import os
import yaml
import subprocess
import random
import time
import socket
from flask import Flask, render_template_string, request

app = Flask(__name__)

TEMPLATE_PATH = "template/kind-custom.yaml"
GENERATED_PATH = "genereate/"

html_template = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <title>실습 환경 생성</title>
  <style>
    body { font-family: sans-serif; padding: 2rem; max-width: 900px; margin: auto; }
    label { display: block; margin-top: 1rem; }
    input, select, textarea { width: 100%; padding: 0.5rem; margin-top: 0.25rem; }
    button { margin-top: 2rem; padding: 0.75rem 1.5rem; font-size: 1rem; }
    .result { margin-top: 2rem; white-space: pre-wrap; background: #f4f4f4; padding: 1rem; border-radius: 5px; }
    .loader {
      border: 6px solid #f3f3f3;
      border-top: 6px solid #3498db;
      border-radius: 50%;
      width: 40px;
      height: 40px;
      animation: spin 1s linear infinite;
      margin: 20px auto;
      display: none;
    }
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    .lab-container { display: flex; }
    .lab-info { width: 25%; padding: 1rem; background: #f9f9f9; border-right: 1px solid #ccc; }
    .lab-terminal { width: 75%; height: 600px; border: none; }
  </style>
</head>
<body>
  <h1>실습 환경 생성</h1>
  <form method=\"post\" action=\"/start-lab\" onsubmit=\"document.getElementById('loader').style.display='block';\">
    <label for=\"username\">사용자 이름</label>
    <input type=\"text\" id=\"username\" name=\"username\" required>

    <label for=\"image\">이미지</label>
    <input type=\"text\" id=\"image\" name=\"image\" value=\"bodlehg/kind-runtime:test\">

    <label for=\"cpu\">CPU (예: 500m, 4)</label>
    <input type=\"text\" id=\"cpu\" name=\"cpu\" value=\"4\">

    <label for=\"memory\">Memory (예: 2Gi)</label>
    <input type=\"text\" id=\"memory\" name=\"memory\" value=\"2Gi\">

    <button type=\"submit\">실습 환경 생성</button>
  </form>

  <div class=\"loader\" id=\"loader\"></div>

  {% if access_url %}
  <div class=\"lab-container\">
    <div class=\"lab-info\">
      <h3>실습 정보</h3>
      <p><strong>Pod:</strong> {{ pod_name }}</p>
      <p><strong>Namespace:</strong> {{ namespace }}</p>
      <p><strong>접속 주소:</strong><br><a href=\"{{ access_url }}\" target=\"_blank\">{{ access_url }}</a></p>
    </div>
    <iframe src=\"{{ access_url }}\" class=\"lab-terminal\"></iframe>
  </div>
  {% elif result %}
    <div class=\"result\">{{ result }}</div>
  {% endif %}
</body>
</html>
"""

def get_used_node_ports():
    try:
        svc_output = subprocess.check_output(
            ["kubectl", "get", "svc", "--all-namespaces", "-o", "jsonpath={..nodePort}"],
            text=True
        )
        ports = [int(p) for p in svc_output.split() if p.isdigit()]
        return set(ports)
    except subprocess.CalledProcessError:
        return set()

def generate_unique_nodeport(start=20000, end=22767, max_attempts=100):
    used_ports = get_used_node_ports()
    for _ in range(max_attempts):
        candidate = random.randint(start, end)
        if candidate not in used_ports:
            return candidate
    raise RuntimeError("사용 가능한 NodePort를 찾을 수 없습니다.")

def generate_random_nodeport():
    return generate_unique_nodeport()

def wait_for_port(host, port, timeout=60, interval=5):
    elapsed = 0
    while elapsed < timeout:
        try:
            with socket.create_connection((host, port), timeout=3):
                return True
        except Exception:
            time.sleep(interval)
            elapsed += interval
    return False

@app.route("/", methods=["GET"])
def index():
    return render_template_string(html_template)

@app.route("/start-lab", methods=["POST"])
def start_lab():
    username = request.form["username"]
    image = request.form["image"]
    cpu = request.form["cpu"]
    memory = request.form["memory"]
    namespace = f"cvpcp-{username}"
    pod_name = f"kind-host-{username}"
    svc_name = f"kind-terminal-svc-{username}"
    node_port = generate_random_nodeport()

    with open(TEMPLATE_PATH, "r") as f:
        docs = list(yaml.safe_load_all(f))

    for doc in docs:
        if doc["kind"] == "Pod":
            doc["metadata"]["name"] = pod_name
            doc["metadata"]["namespace"] = namespace
            doc["metadata"]["labels"]["app"] = pod_name
            doc["spec"]["containers"][0]["image"] = image
            doc["spec"]["containers"][0]["resources"]["requests"]["cpu"] = cpu
            doc["spec"]["containers"][0]["resources"]["requests"]["memory"] = memory
            doc["spec"]["containers"][0]["resources"]["limits"]["cpu"] = str(int(cpu) * 5)
            doc["spec"]["containers"][0]["resources"]["limits"]["memory"] = "20Gi"
        elif doc["kind"] == "Service":
            doc["metadata"]["name"] = svc_name
            doc["metadata"]["namespace"] = namespace
            doc["spec"]["selector"]["app"] = pod_name
            doc["spec"]["ports"][0]["nodePort"] = node_port
        elif doc["kind"] == "ClusterRoleBinding":
            doc["subjects"][0]["namespace"] = namespace

    custom_generated_path = os.path.join(GENERATED_PATH, f"{username}.yaml")
    os.makedirs(os.path.dirname(custom_generated_path), exist_ok=True)
    with open(custom_generated_path, "w") as f:
        yaml.dump_all(docs, f)

    try:
        subprocess.run(["kubectl", "create", "namespace", namespace], check=True)
        subprocess.run(["kubectl", "apply", "-f", custom_generated_path], check=True)
        node_ip = subprocess.check_output([
            "kubectl", "get", "nodes", "-o", "jsonpath={.items[0].status.addresses[0].address}"
        ]).decode().strip()
        access_url = f"http://{node_ip}:{node_port}"

        # Apply 성공 메시지 즉시 출력
        result_msg = f"✔ 실습 환경 생성 명령 성공! \n접속 가능 여부 확인 중..."

        # ttyd 서비스 대기
        ready = wait_for_port(node_ip, node_port, timeout=60, interval=5)
        if ready:
            return render_template_string(html_template, access_url=access_url, pod_name=pod_name, namespace=namespace)
        else:
            result_msg += f"\n⚠ 접속 불가: 수동 확인 필요 → {access_url}"
            return render_template_string(html_template, result=result_msg)
    except subprocess.CalledProcessError as e:
        result_msg = f"❌ kubectl 오류:\n{e}"
        return render_template_string(html_template, result=result_msg)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000, use_reloader=False)
