const API_URL = "http://localhost:8000";

async function sendMessage() {
    const input = document.getElementById("userInput");
    const question = input.value.trim();
    
    if (!question) return;
    
    // Show user message
    addMessage(question, "user");
    input.value = "";
    
    // Show loading indicator
    const loadingId = addMessage("Thinking... 🤔", "loading");
    
    try {
        const response = await fetch(`${API_URL}/ask`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question })
        });
        
        const data = await response.json();
        
        // Remove loading message
        removeMessage(loadingId);
        
        // Show bot answer
        addMessage(data.answer, "bot");
        
    } catch (error) {
        removeMessage(loadingId);
        addMessage("Sorry, I couldn't connect to the server. Please try again.", "bot");
    }
}

function addMessage(text, type) {
    const chatBox = document.getElementById("chatBox");
    const msgId = "msg-" + Date.now();
    
    const div = document.createElement("div");
    div.id = msgId;
    div.className = `message ${type}-message`;
    div.textContent = text;
    
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
    
    return msgId;
}

function removeMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function handleKeyPress(event) {
    if (event.key === "Enter") sendMessage();
}

function askSample(question) {
    document.getElementById("userInput").value = question;
    sendMessage();
}