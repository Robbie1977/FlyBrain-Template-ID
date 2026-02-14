# ============================================================
# FlyBrain Template ID — Alignment & Review Server
# ============================================================
# Installs CMTK (https://www.nitrc.org/projects/cmtk) from the
# NeuroDebian repository, plus Node.js and Python dependencies.
# ============================================================

FROM node:20-bookworm-slim

# Install wget/gnupg first so we can add the NeuroDebian repo
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget gnupg2 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Add NeuroDebian repository (provides CMTK from https://www.nitrc.org/projects/cmtk)
RUN wget -q -O- http://neuro.debian.net/lists/bookworm.us-tn.libre \
        > /etc/apt/sources.list.d/neurodebian.sources.list \
    && apt-key adv --recv-keys --keyserver hkps://keyserver.ubuntu.com 0xA5D32F012649A5A9

# Install CMTK, Python, and runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        cmtk \
        python3 python3-pip python3-venv \
        procps \
    && rm -rf /var/lib/apt/lists/*

# CMTK installs to /usr/lib/cmtk/bin — add to PATH
ENV PATH="/usr/lib/cmtk/bin:${PATH}"

# Verify CMTK installed correctly
RUN registration --version || true

# ---- Application setup ----
WORKDIR /app

# Install Node.js dependencies first (cache layer)
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev 2>/dev/null || npm install --omit=dev

# Create Python venv and install packages
RUN python3 -m venv /app/venv
ENV VIRTUAL_ENV=/app/venv
ENV PATH="/app/venv/bin:${PATH}"
RUN pip install --no-cache-dir \
        tifffile \
        pynrrd \
        numpy \
        scipy \
        matplotlib

# Copy template NRRD files (originals + LPS variants)
COPY JRC2018U_template.nrrd JRCVNC2018U_template.nrrd ./
COPY JRC2018U_template_lps.nrrd JRCVNC2018U_template_lps.nrrd ./

# Copy application code
COPY server.js ./
COPY public/ ./public/
COPY align_single_cmtk.sh align_all_cmtk.sh align_cmtk.sh ./
COPY get_image_data.py apply_rotation.py reset_rotation.py ./
COPY split_channels.py convert_tiff_to_nrrd.py identify_template.py ./
COPY update_alignment_progress.py ./
COPY orientations.json* ./
COPY docker-entrypoint.sh ./

RUN chmod +x align_single_cmtk.sh align_all_cmtk.sh align_cmtk.sh docker-entrypoint.sh

# ---- Volume mount points ----
# /data/input    — Drop TIFF files here (organisation subdirs supported)
# /data/processing — Intermediate files (channels, nrrd, xforms, backups)
# /data/output   — Final aligned NRRD files + thumbnails
VOLUME ["/data/input", "/data/processing", "/data/output"]

EXPOSE 3000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["node", "server.js"]
