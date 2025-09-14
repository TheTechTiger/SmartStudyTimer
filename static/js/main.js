// Timer variables
let currentSession = null;
let timerInterval = null;
let timeLeft = 0;
let isBreak = false;
let currentMode = 'focus';
let isPaused = false;

const modes = {
    focus: { study: 25, break: 5 },
    deep: { study: 50, break: 10 },
    custom: { study: 25, break: 5 }
};

// Timer functions
function updateTimer(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    document.getElementById('timer').textContent = 
        `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
}

function showNotification(message) {
    const notification = document.getElementById('notification');
    document.getElementById('notificationText').textContent = message;
    notification.classList.add('show');
    setTimeout(() => {
        notification.classList.remove('show');
    }, 5000);
}

async function startSession() {
    const mode = currentMode;
    const duration = isBreak ? 
        modes[mode].break * 60 : 
        modes[mode].study * 60;

    const response = await fetch('/api/start-session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, duration })
    });
    const data = await response.json();
    currentSession = data.session_id;
    return duration;
}

async function endSession() {
    if (currentSession) {
        const response = await fetch('/api/end-session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                session_id: currentSession,
                duration: modes[currentMode].study * 60
            })
        });
        const data = await response.json();
        showNotification(data.study_tip);
        
        // Play the TTS audio
        const audio = new Audio('/static/audio/notification.mp3');
        audio.play();
    }
}

// Load achievements
async function loadAchievements() {
    const response = await fetch('/api/achievements');
    const achievements = await response.json();
    const container = document.getElementById('achievements');
    container.innerHTML = achievements.map(achievement => `
        <div class="bg-gray-50 p-4 rounded-lg ${achievement.earned ? 'border-2 border-green-500' : ''}">
            <img src="/static/${achievement.badge_image}" alt="${achievement.name}" class="w-12 h-12 mb-2">
            <h3 class="font-semibold">${achievement.name}</h3>
            <p class="text-sm text-gray-600">${achievement.description}</p>
        </div>
    `).join('');
}

// Load study groups
async function loadStudyGroups() {
    const response = await fetch('/api/study-groups');
    const groups = await response.json();
    const container = document.getElementById('studyGroups');
    container.innerHTML = groups.map(group => `
        <div class="bg-gray-50 p-4 rounded-lg">
            <h3 class="font-semibold">${group.name}</h3>
            <p class="text-sm text-gray-600">${group.member_count} members</p>
            ${group.is_member ? 
                `<button class="mt-2 bg-green-100 text-green-600 px-3 py-1 rounded text-sm" disabled>
                    Member
                </button>` :
                `<button onclick="joinGroup(${group.id}, this)" 
                    class="mt-2 bg-indigo-100 text-indigo-600 px-3 py-1 rounded text-sm hover:bg-indigo-200">
                    Join Group
                </button>`
            }
        </div>
    `).join('');
}

// Join study group
async function joinGroup(groupId, buttonElement) {
    try {
        const response = await fetch(`/api/study-groups/${groupId}/join`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Update button to show membership
            const groupDiv = buttonElement.closest('.bg-gray-50');
            buttonElement.outerHTML = `
                <button class="mt-2 bg-green-100 text-green-600 px-3 py-1 rounded text-sm" disabled>
                    Member
                </button>
            `;
            
            // Update member count
            const memberCountElem = groupDiv.querySelector('p');
            memberCountElem.textContent = `${data.member_count} members`;
            
            showNotification('Successfully joined the group!');
        } else {
            showNotification(data.message || 'Failed to join group');
        }
    } catch (error) {
        showNotification('Error joining group');
        console.error('Error:', error);
    }
}

// Logout functionality
function logout() {
    if (confirm('Are you sure you want to logout?')) {
        // Use POST method for logout
        fetch('/logout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin'  // Include cookies
        }).then(response => {
            if (response.ok) {
                window.location.href = '/';  // Redirect to home page after successful logout
            } else {
                showNotification('Logout failed. Please try again.');
            }
        }).catch(error => {
            console.error('Logout error:', error);
            showNotification('Logout failed. Please try again.');
        });
    }
}

// Initialize everything when the document is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Timer button events
    document.getElementById('startBtn').addEventListener('click', async () => {
        timeLeft = await startSession();
        updateTimer(timeLeft);
        
        timerInterval = setInterval(() => {
            if (!isPaused) {
                timeLeft--;
                updateTimer(timeLeft);
                
                if (timeLeft <= 0) {
                    clearInterval(timerInterval);
                    if (isBreak) {
                        showNotification("Break's over! Time to study!");
                        isBreak = false;
                    } else {
                        endSession();
                        showNotification("Great job! Time for a break!");
                        isBreak = true;
                    }
                    timeLeft = isBreak ? 
                        modes[currentMode].break * 60 : 
                        modes[currentMode].study * 60;
                    startSession();
                }
            }
        }, 1000);

        document.getElementById('startBtn').classList.add('hidden');
        document.getElementById('pauseBtn').classList.remove('hidden');
    });

    document.getElementById('pauseBtn').addEventListener('click', () => {
        isPaused = true;
        document.getElementById('pauseBtn').classList.add('hidden');
        document.getElementById('resumeBtn').classList.remove('hidden');
    });

    document.getElementById('resumeBtn').addEventListener('click', () => {
        isPaused = false;
        document.getElementById('resumeBtn').classList.add('hidden');
        document.getElementById('pauseBtn').classList.remove('hidden');
    });

    document.getElementById('resetBtn').addEventListener('click', () => {
        clearInterval(timerInterval);
        isPaused = false;
        isBreak = false;
        timeLeft = modes[currentMode].study * 60;
        updateTimer(timeLeft);
        document.getElementById('startBtn').classList.remove('hidden');
        document.getElementById('pauseBtn').classList.add('hidden');
        document.getElementById('resumeBtn').classList.add('hidden');
    });

    // Mode selection
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.mode-btn').forEach(b => {
                b.classList.remove('bg-indigo-600', 'text-white');
                b.classList.add('bg-indigo-100', 'text-indigo-600');
            });
            btn.classList.remove('bg-indigo-100', 'text-indigo-600');
            btn.classList.add('bg-indigo-600', 'text-white');
            
            currentMode = btn.dataset.mode;
            document.getElementById('customSettings').classList.toggle('hidden', currentMode !== 'custom');
            
            if (currentMode === 'custom') {
                modes.custom.study = parseInt(document.getElementById('customStudyDuration').value);
                modes.custom.break = parseInt(document.getElementById('customBreakDuration').value);
            }
            
            timeLeft = modes[currentMode].study * 60;
            updateTimer(timeLeft);
        });
    });

    // Custom duration inputs
    document.getElementById('customStudyDuration').addEventListener('change', (e) => {
        modes.custom.study = parseInt(e.target.value);
        if (currentMode === 'custom') {
            timeLeft = modes.custom.study * 60;
            updateTimer(timeLeft);
        }
    });

    document.getElementById('customBreakDuration').addEventListener('change', (e) => {
        modes.custom.break = parseInt(e.target.value);
    });

    // Create study group
    document.getElementById('createGroupBtn').addEventListener('click', async () => {
        const groupName = prompt('Enter group name:');
        if (groupName) {
            await fetch('/api/study-groups', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: groupName })
            });
            loadStudyGroups();
        }
    });

    // Dismiss notification
    document.getElementById('dismissNotification').addEventListener('click', () => {
        document.getElementById('notification').classList.remove('show');
    });

    // Initial loads
    loadAchievements();
    loadStudyGroups();
});