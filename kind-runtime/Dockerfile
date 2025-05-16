# Stage 1: extract ttyd from official image
FROM tsl0922/ttyd AS ttyd-bin

# Stage 2: main environment
FROM docker:24.0.2-dind

ENV KIND_VERSION=v0.22.0
ENV KUBECTL_VERSION=v1.29.0

# Install dependencies
RUN apk add --no-cache bash curl

# Install kind
RUN curl -Lo /usr/local/bin/kind https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-linux-amd64 && \
    chmod +x /usr/local/bin/kind

# Install kubectl
RUN curl -Lo kubectl https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl && \
    chmod +x kubectl && mv kubectl /usr/local/bin/

# Copy ttyd from official image
COPY --from=ttyd-bin /usr/bin/ttyd /usr/local/bin/ttyd


# Entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
