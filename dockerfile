FROM docker.io/ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV KIOSK_URL="https://www.google.com"
ENV VITE_APP_WS_SERVER_URL="http://excalidraw-room.localhost:8080/"
ENV ROOM_DOMAIN_ADDRESS="excalidraw-room.localhost"
ENV DOMAIN_ADDRESS="localhost"
ENV SERVICE_URL="http://localhost:8080"

ENV AWS_ACCESS_KEY_ID=""
ENV AWS_SECRET_ACCESS_KEY=""
ENV AWS_SESSION_TOKEN=""
ENV AWS_REGION="us-east-1"
ENV OPENAI_API_KEY=""
ENV GEMINI_API_KEY=""
ENV API_PROVIDER="bedrock"

ENV ROOM_SERVER_MAX_AGE=3600
ENV ROOM_SERVER_MAX_CLIENTS=10
ENV STREAMLIT_SERVER_PORT=3003

ARG DISPLAY_NUM=1
ARG HEIGHT=768
ARG WIDTH=1024
ENV DISPLAY_NUM=$DISPLAY_NUM
ENV HEIGHT=$HEIGHT
ENV WIDTH=$WIDTH

RUN apt-get update \
    && apt-get -y upgrade \
    && apt-get install -y \
    wget \
    gnupg2 \
    supervisor \
    fonts-liberation \
    libu2f-udev \
    libvulkan1 \
    nano \
    # UI Requirements
    fluxbox \
    xdg-utils \
    xvfb \
    xterm \
    xdotool \
    scrot \
    imagemagick \
    sudo \
    mutter \
    x11vnc \
    # Python/pyenv reqs
    build-essential \
    libssl-dev  \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    curl \
    git \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev \
    gettext \
    # Network tools
    net-tools \
    netcat \
    nginx \
    # PPA req
    software-properties-common \
    # Userland apps
    && add-apt-repository ppa:mozillateam/ppa \
    && add-apt-repository ppa:xtradeb/apps \
    && apt-get install -y --no-install-recommends \
    libreoffice \
    firefox-esr \
    chromium \
    x11-apps \
    xpdf \
    gedit \
    xpaint \
    tint2 \
    galculator \
    pcmanfm \
    unzip \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# setup user
ENV USERNAME=root
ENV HOME=/home/$USERNAME
RUN echo "${USERNAME} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
WORKDIR $HOME

# setup python
RUN git clone https://github.com/pyenv/pyenv.git ~/.pyenv && \
    cd ~/.pyenv && src/configure && make -C src && cd .. && \
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc && \
    echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc && \
    echo 'eval "$(pyenv init -)"' >> ~/.bashrc
ENV PYENV_ROOT="$HOME/.pyenv"
ENV PATH="$PYENV_ROOT/bin:$PATH"
ENV PYENV_VERSION_MAJOR=3
ENV PYENV_VERSION_MINOR=11
ENV PYENV_VERSION_PATCH=6
ENV PYENV_VERSION=$PYENV_VERSION_MAJOR.$PYENV_VERSION_MINOR.$PYENV_VERSION_PATCH
RUN eval "$(pyenv init -)" && \
    pyenv install $PYENV_VERSION && \
    pyenv global $PYENV_VERSION && \
    pyenv rehash

ENV PATH="$HOME/.pyenv/shims:$HOME/.pyenv/bin:$PATH"

RUN python -m pip install --upgrade pip==23.1.2 setuptools==58.0.4 wheel==0.40.0 && \
    python -m pip config set global.disable-pip-version-check true


# Install Node.js (version 18.x recommended for compatibility)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

RUN git clone https://github.com/novnc/noVNC.git /opt/novnc \
    && git clone https://github.com/novnc/websockify /opt/novnc/utils/websockify \
    && mkdir ~/.vnc \
    && x11vnc -storepasswd chrome ~/.vnc/passwd \
    && cp /opt/novnc/vnc.html /opt/novnc/index.html 
 
RUN git clone https://github.com/excalidraw/excalidraw.git /opt/excalidraw \
    && cd /opt/excalidraw \
    && npm -g install yarn \
    && yarn install

RUN git clone https://github.com/excalidraw/excalidraw-room.git /opt/excalidraw-room \
    && cd /opt/excalidraw-room \
    && npm -g install yarn \
    && yarn install 

RUN git clone https://github.com/anthropics/anthropic-quickstarts.git /opt/anthropic-quickstart \
    && cp -r /opt/anthropic-quickstart/computer-use-demo/image/* ~/ \
    && cp -r /opt/anthropic-quickstart/computer-use-demo/computer_use_demo ~/ \
    && python -m pip install -r ~/computer_use_demo/requirements.txt

COPY excalidraw/index.html.template /opt/excalidraw/excalidraw-app
COPY excalidraw/system_prompt.txt /opt/excalidraw/excalidraw-app
COPY computer_use_demo /home/root
COPY nginx.conf.template /etc/nginx/nginx.conf.template
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh




COPY socket-server /opt/socket-server
WORKDIR /opt/socket-server
RUN python -m pip install -r requirements.txt

RUN mkdir -p /etc/chromium/policies/managed && \
    echo '{\n\
    "AutoplayAllowed": true,\n\
    "PopupsAllowed": true,\n\
    "RemoteAccessHostFirewallTraversal": true,\n\
    "AudioProcessHighPriorityEnabled": true,\n\
    "TranslateEnabled": true,\n\
    "DefaultBrowserSettingEnabled": false,\n\
    "RestoreOnStartup": 4,\n\
    "HomepageIsNewTabPage": false,\n\
    "CommandLineFlagSecurityWarningsEnabled": false,\n\
    "PasswordManagerEnabled": false\n\
    }' > /etc/chromium/policies/managed/policy.json

RUN echo "#!/bin/bash\n\
    Xvfb :1 -screen 0 1920x1080x24 &\n\
    export DISPLAY=:1\n\
    fluxbox &\n\
    x11vnc -forever -nopw -shared -rfbport 5900 -display :1 &\n\
    /usr/bin/chromium \
        --no-sandbox \
        --disable-notifications \
        --disable-translate \
        --noerrdialogs \
        --no-first-run \
        --fast \
        --fast-start \
        --disable-features=TranslateUI \
        --disable-gpu \
        --disable-sync \
        --start-maximized \
        --user-data-dir=/data \
        --no-default-browser-check \
        --touch-events=enabled \
        --disable-pinch \
        --overscroll-history-navigation=0 \
        --show-component-extension-options \ 
        \"\${KIOSK_URL}\"" > /start.sh \
    && chmod +x /start.sh

RUN mkdir -p /data && chmod 777 /data

RUN echo "[supervisord]\n\
    nodaemon=true\n\
    user=root\n\n\
    [program:novnc]\n\
    command=/opt/novnc/utils/novnc_proxy --vnc localhost:5900 --listen 3001\n\
    autorestart=true\n\
    user=root\n\n\
    [program:excalidraw]\n\
    command=yarn start --host=0.0.0.0\n\
    directory=/opt/excalidraw\n\
    autorestart=true\n\
    user=root\n\n\
    [program:excalidraw-room]\n\
    command=yarn start:dev\n\
    directory=/opt/excalidraw-room\n\
    autorestart=true\n\
    user=root\n\n\
    [program:chrome]\n\
    command=/start.sh\n\
    autorestart=true\n\
    user=root\n\
    environment=HOME=\"/root\",USER=\"root\"\n\
    redirect_stderr=true\n\
    stdout_logfile=/var/log/chrome.log\n\n\
    [program:computer-use-demo-streamlit]\n\
    command=python -m streamlit run computer_use_demo/streamlit.py > /tmp/streamlit_stdout.log &\n\
    autorestart=true\n\
    user=root\n\
    directory=/home/root\n\n\
    [program:socket-server]\n\
    command=python WebSrvr.py > /tmp/socket-server_stdout.log &\n\
    autorestart=true\n\
    user=root\n\
    directory=/opt/socket-server\n\n\
    [program:nginx]\n\
    command=nginx -g 'daemon off;'\n\
    autorestart=true\n\
    priority=5\n\
    user=root\n\
    stdout_logfile=/var/log/nginx/access.log\n\
    stderr_logfile=/var/log/nginx/error.log" > /etc/supervisor/conf.d/supervisord.conf

EXPOSE 8080
# 3000 - excalidraw
# 3001 - novnc
# 3002 - excalidraw-room
# 3003 - anthropic
# 3004 - socket-server

#CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
ENTRYPOINT ["/entrypoint.sh"]
