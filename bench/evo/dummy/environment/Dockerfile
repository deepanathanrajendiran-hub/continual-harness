FROM ubuntu:22.04
COPY probe.sh /opt/evo-check/probe.sh
# setup.sh must remove this file before round 1's agent phase.
RUN chmod 0755 /opt/evo-check/probe.sh && touch /tmp/evo-image-file
WORKDIR /app
