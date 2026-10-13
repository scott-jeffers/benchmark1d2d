# Pinned EPA SWMM 5.2.4 reference-engine image (placeholder scaffold).
#
# Multi-stage intent (implemented once the binary is vendored in CI):
#   1. builder  — fetch + compile EPA SWMM 5.2.4 from the official source tarball
#   2. runtime  — copy only the swmm5 binary into a minimal image
#
# Official download (document; do not curl blindly in local scaffolds without
# verifying the published SHA-256):
#   https://www.epa.gov/water-research/storm-water-management-model-swmm
#   Source archive historically named like:
#     swmm524-source.zip  (EPA SWMM 5.2.4)
#
# Until Docker + the pinned binary are available on the runner, this file is a
# documented placeholder. Regenerate SHA256SUMS in CI once the binary is vendored.

# --- Stage 1: builder (placeholder) ---
# FROM debian:bookworm-slim AS builder
# RUN apt-get update && apt-get install -y --no-install-recommends \
#       build-essential ca-certificates curl unzip \
#     && rm -rf /var/lib/apt/lists/*
# WORKDIR /src
# # PLACEHOLDER: fetch EPA SWMM 5.2.4 source, verify checksum, compile swmm5
# # RUN curl -fsSL -o swmm524-source.zip "<EPA_URL>" \
# #  && echo "<published-sha256>  swmm524-source.zip" | sha256sum -c - \
# #  && unzip swmm524-source.zip \
# #  && make -C <src-dir> \
# #  && install -m 0755 <src-dir>/swmm5 /usr/local/bin/swmm5

# --- Stage 2: runtime (placeholder) ---
FROM debian:bookworm-slim
# COPY --from=builder /usr/local/bin/swmm5 /usr/local/bin/swmm5
#
# Placeholder entrypoint: once the binary is present, CMD invokes swmm5.
# Local / CI without Docker+SWMM should not expect this image to build yet.
LABEL org.openwmm.reference_engine="SWMM" \
      org.openwmm.reference_version="5.2.4" \
      org.openwmm.note="PLACEHOLDER — pin binary hash in SHA256SUMS after vendoring"

# CMD runs swmm5 (args: inp rpt out) when the binary is installed.
CMD ["swmm5"]
