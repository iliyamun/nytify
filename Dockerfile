FROM node:22-bookworm-slim AS javascript
FROM mcr.microsoft.com/dotnet/sdk:8.0-bookworm-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY scripts/fetch_engine.py scripts/fetch_engine.py
RUN python3 scripts/fetch_engine.py /engine
COPY plugin/ plugin/
RUN dotnet build plugin/MusicBot.csproj -c Release -p:EnginePath=/engine -o /plugin --nologo

FROM mcr.microsoft.com/dotnet/runtime:8.0-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv ffmpeg libopus0 ca-certificates libicu72 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s "$(find /usr/lib -name libopus.so.0 -print -quit)" /usr/lib/libopus.so \
    && python3 -m venv /opt/music-python \
    && useradd --uid 10001 --create-home music
COPY requirements.txt /app/requirements.txt
COPY --from=javascript /usr/local/bin/node /usr/local/bin/node
RUN /opt/music-python/bin/pip install --no-cache-dir -r /app/requirements.txt
COPY --from=build /engine/ /app/engine/
COPY --from=build /plugin/MusicBot.dll /app/plugins/MusicBot.dll
COPY musicbot/ /app/musicbot/
COPY LICENSE THIRD_PARTY_NOTICES.md /app/
COPY licenses/ /app/licenses/
COPY scripts/entrypoint.sh /app/entrypoint.sh
RUN mkdir -p /data && chown music:music /data && chmod +x /app/entrypoint.sh
ENV MUSIC_PYTHON=/opt/music-python/bin/python3 \
    MUSIC_RESOLVER=/app/musicbot/resolver.py \
    DOTNET_ROLL_FORWARD=Major \
    DOTNET_EnableDiagnostics=0
WORKDIR /data
USER music
ENTRYPOINT ["/app/entrypoint.sh"]
