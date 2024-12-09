document.addEventListener('DOMContentLoaded', () => {
    try {

      const socket = io.connect()

      socket.off('toggle'); 
      socket.on('toggle', function(data) {
      console.log('Received toggle event:', data);
        if (data.mode) {
            toggleMode(data.mode);
        } else {
            console.warn('No mode provided in toggle event:', data);
        }
      });


      const drawContainer = document.getElementById('excalidraw');
      const drawButton = document.getElementById('draw-button');          
      const anthropicContainer = document.getElementById('anthropic');
      const anthropicButton = document.getElementById('anthropic-button');
      const aiContainer = document.getElementById('ai');
      const aiButton = document.getElementById('ai-button');
      const chatContainer = document.getElementById('chat');
      const chatButton = document.getElementById('chat-button')
      const fullscreenButton = document.getElementById('fullscreen-button');

      drawContainer.style.pointerEvents = 'none';
      
      let drawMode = false;
      let controlMode = false;
      let aiMode = false;
      let chatMode = false;
      let activeMode = false;

      // Full Screen Toggle
      fullscreenButton.addEventListener('click', () => {
        if (!document.fullscreenElement) {
          document.documentElement.requestFullscreen();
          fullscreenButton.textContent = 'Exit Full Screen';
        } else {
          document.exitFullscreen();
          fullscreenButton.textContent = 'Full Screen';
        }
      });

      function toggleMode(mode) { 
        const modes = {
          draw: { flag: "drawMode", container: drawContainer, button: drawButton },
          ai: { flag: "aiMode", container: aiContainer, button: aiButton },
          chat: { flag: "chatMode", container: chatContainer, button: chatButton },
          anthropic: { flag: "controlMode", container: anthropicContainer, button: anthropicButton },
        };
      
        for (const key in modes) {
          const { flag, container, button } = modes[key];
          window[flag] = false;
          container.classList.remove("visible");
          container.classList.add("invisible");
          button.textContent = `Show ${key.charAt(0).toUpperCase() + key.slice(1)}`;
          if (key === "draw") container.style.pointerEvents = "none";
        }

        if (activeMode !== mode) {
          const { flag, container, button } = modes[mode];
          window[flag] = true;
          activeMode = mode;
          container.classList.remove("invisible");
          container.classList.add("visible");
          button.textContent = `Hide ${mode.charAt(0).toUpperCase() + mode.slice(1)}`;
          if (mode === "draw") container.style.pointerEvents = "auto"; // Enable draw-specific behavior
        } else {
          activeMode = false;
        }
      };

      drawButton.addEventListener("click", () => {
        socket.emit('toggle', { mode: 'draw' });
        toggleMode("draw");
      });
      
      aiButton.addEventListener("click", () => {
        socket.emit('toggle', { mode: 'ai' });
        toggleMode("ai");
      });
      
      chatButton.addEventListener("click", () => {
        socket.emit('toggle', { mode: 'chat' });
        toggleMode("chat");
      });
      
      anthropicButton.addEventListener("click", () => {
        socket.emit('toggle', { mode: 'anthropic' });
        toggleMode("anthropic");
      });
      

    } catch (error) {
      console.error('Initialization error:', error);
    }
});
