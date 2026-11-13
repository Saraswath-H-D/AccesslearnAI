FROM python:3.11-slim

# libgl1/libglib2.0-0: required by opencv-python (visual_service.py) for
# video frame extraction; the slim base image lacks them.
# curl/unzip: needed to install Deno below.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Deno: JS runtime yt-dlp (via yt-dlp-ejs, see requirements.txt) needs to
# solve YouTube's playback challenge for some videos -- without it,
# yt-dlp misreports those videos as unavailable.
RUN curl -fsSL https://deno.land/install.sh | sh
ENV DENO_INSTALL=/root/.deno
ENV PATH="$DENO_INSTALL/bin:$PATH"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV HF_HOME=/app/.hf_cache
ENV PORT=8000
EXPOSE 8000

CMD ["python", "run.py"]
