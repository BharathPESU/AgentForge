const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const agentSelect = document.getElementById('agent-select');
const agentInfo = document.getElementById('agent-info');
const currentAgentDisplay = document.getElementById('current-agent-display');
const headerModeBadge = document.getElementById('header-mode-badge');
const connectionStatus = document.getElementById('connection-status');

let registeredAgentsMap = {};

// Load agent definitions dynamically from backend
async function loadAgentsAndHealth() {
    try {
        const res = await fetch('/agents');
        if (res.ok) {
            const data = await res.json();
            
            connectionStatus.className = 'status-badge status-online';
            connectionStatus.querySelector('.status-text').innerText = 'System Ready';

            if (data.project && data.project.name) {
                const brandTitle = document.querySelector('.brand-text h2');
                if (brandTitle) brandTitle.innerText = data.project.name;
            }

            // Populate agent select dynamically
            if (Array.isArray(data.agents)) {
                agentSelect.innerHTML = '<option value="auto">Auto-Route (Orchestrator)</option>';
                registeredAgentsMap = {};

                data.agents.forEach(ag => {
                    registeredAgentsMap[ag.id] = ag;
                    const opt = document.createElement('option');
                    opt.value = ag.id;
                    opt.textContent = `${ag.name} (${ag.id})`;
                    agentSelect.appendChild(opt);
                });
            }
        } else {
            throw new Error('Failed to load agents');
        }
    } catch (e) {
        connectionStatus.className = 'status-badge status-offline';
        connectionStatus.querySelector('.status-text').innerText = 'Backend Offline';
    }
}

loadAgentsAndHealth();

// Update agent details when selection changes
agentSelect.addEventListener('change', () => {
    const val = agentSelect.value;

    if (val === 'auto') {
        agentInfo.innerHTML = `
            <div class="info-title"><i class="fas fa-brain"></i> Auto-Route (Orchestrator)</div>
            <div class="info-desc">Orchestrator dynamically routes queries to the optimal agent or executes parallel pipeline.</div>
        `;
        currentAgentDisplay.innerText = "Research Assistant Collective";
        headerModeBadge.innerText = "Auto-Routing Active";
    } else {
        const ag = registeredAgentsMap[val] || {};
        agentInfo.innerHTML = `
            <div class="info-title"><i class="fas fa-robot"></i> ${ag.name || val}</div>
            <div class="info-desc">${ag.description || ag.role || 'Specialized AI Agent'}</div>
        `;
        currentAgentDisplay.innerText = `${ag.name || val}`;
        headerModeBadge.innerText = `Direct Agent Mode (${val})`;
    }
});

// Auto-expand textarea
userInput.addEventListener('input', () => {
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
});

function appendMessage(role, text, senderLabel = null) {
    const div = document.createElement('div');
    div.className = `message ${role === 'user' ? 'user-message' : 'bot-message'}`;

    const icon = role === 'user' ? 'fa-user' : 'fa-robot';
    const name = senderLabel || (role === 'user' ? 'You' : 'ADK Agent');

    div.innerHTML = `
        <div class="avatar"><i class="fas ${icon}"></i></div>
        <div class="message-content">
            <div class="sender-name">
                ${name}
                ${senderLabel ? `<span class="sender-badge">${role === 'user' ? 'User' : 'Agent'}</span>` : ''}
            </div>
            <p>${escapeHtml(text)}</p>
        </div>
    `;

    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTypingIndicator() {
    const div = document.createElement('div');
    div.className = 'message bot-message typing-container';
    div.id = 'typing-indicator';
    div.innerHTML = `
        <div class="avatar"><i class="fas fa-robot"></i></div>
        <div class="message-content typing-indicator">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

function escapeHtml(unsafe) {
    if (typeof unsafe !== 'string') return unsafe;
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    appendMessage('user', text);
    userInput.value = '';
    userInput.style.height = 'auto';

    const agentId = agentSelect.value === 'auto' ? null : agentSelect.value;
    showTypingIndicator();

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                agent_id: agentId,
                auto_route: agentId === null
            })
        });

        removeTypingIndicator();

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            appendMessage('bot', `Error ${response.status}: ${errData.detail || 'Server request failed'}`);
            return;
        }

        const data = await response.json();
        
        let reply = '';
        let agentLabel = 'ADK Orchestrator';

        if (data.agent_name) {
            agentLabel = `${data.agent_name} (${data.assigned_agent || data.agent_id})`;
        } else if (data.agent_id) {
            agentLabel = `Agent: ${data.agent_id}`;
        }

        if (data.result?.response) {
            reply = data.result.response;
        } else if (data.final_response) {
            reply = data.final_response;
            if (data.critic_verdict) {
                reply += `\n\n--- Critic Verdict ---\n${data.critic_verdict}`;
            }
        } else if (typeof data.result === 'string') {
            reply = data.result;
        } else if (data.response) {
            reply = data.response;
        } else {
            reply = JSON.stringify(data, null, 2);
        }

        appendMessage('bot', reply, agentLabel);
    } catch (error) {
        removeTypingIndicator();
        appendMessage('bot', "Error connecting to the agent server. Please check backend status.");
    }
}

sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
