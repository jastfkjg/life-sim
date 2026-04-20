// Life Sim - Game Logic

// 获取当前页面的origin，用于API请求
const API_URL = window.location.origin + "/api";

let gameState = {
    name: "",
    gender: "",
    age: 18,
    stats: {
        hp: 50,          // 健康 0-100 归0死亡
        money: 50,       // 金钱 0-100
        happiness: 50,   // 快乐 0-100
        career: 30,      // 事业 0-100
        social: 30,      // 社交 0-100
        family: 20,      // 家庭 0-100 结婚生子
        friends: 30,     // 朋友 0-100
        love: 0,         // 爱情 0-100
        loneliness: 20,  // 孤独 0-100（高不好）
        freedom: 60,     // 自由 0-100
        sanity: 70       // 精神/理智 0-100 归0自杀
    },
    history: [],
    milestones: [],
    isGameOver: false
};

function $(id) {
    return document.getElementById(id);
}

function showScreen(screenId) {
    document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
    $(screenId).classList.add("active");
}

function startGame() {
    const name = $("player-name").value.trim();
    const gender = $("player-gender").value;
    const age = parseInt($("player-age").value) || 18;

    if (!name) {
        alert("请输入你的名字");
        return;
    }
    if (age < 1 || age >= 60) {
        alert("年龄需要在1-59之间");
        return;
    }

    gameState.name = name;
    gameState.gender = gender;
    gameState.age = age;
    gameState.stats = {
        hp: 50, money: 50, happiness: 50, career: 30, social: 30,
        family: 20, friends: 30, love: 0, loneliness: 20, freedom: 60,
        sanity: 70
    };
    gameState.history = [];
    gameState.milestones = [];
    gameState.isGameOver = false;

    $("character-name").textContent = name;
    $("character-age").textContent = `${age}岁`;

    showScreen("game-screen");

    generateInitialStory();
}

async function generateInitialStory() {
    $("event-text").textContent = "正在书写你的身世...";

    try {
        const res = await fetch(`${API_URL}/history`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ age: gameState.age, gender: gameState.gender, stats: gameState.stats })
        });
        const data = await res.json();

        gameState.history.push(data.history);
        $("event-text").textContent = data.history;
    } catch (e) {
        const backstory = "出生于普通家庭，从小镇来到大城市闯荡";
        gameState.history.push(backstory);
        $("event-text").textContent = backstory;
    }

    setTimeout(() => {
        addHistory(`你${gameState.age}岁了，${gameState.history[0]}`);
        nextTurn();
    }, 2000);
}

async function nextTurn() {
    if (gameState.isGameOver) return;

    gameState.age++;
    $("character-age").textContent = `${gameState.age}岁`;

    if (gameState.age >= 80) {
        endGame("寿终正寝", "你安详地走完了这一生");
        return;
    }

    // 被动属性变化
    applyPassiveEffects();
    if (gameState.isGameOver) return;

    $("event-text").textContent = "命运的齿轮开始转动...";
    $("choices-container").innerHTML = "";
    $("continue-btn").classList.add("hidden");

    try {
        const res = await fetch(`${API_URL}/event`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                age: gameState.age,
                stats: gameState.stats,
                history: gameState.history
            })
        });

        const data = await res.json();
        if (data.error) throw new Error(data.error);

        displayEvent(data);
    } catch (e) {
        console.error("获取事件失败:", e);
        displayEvent({
            event: "人生的十字路口出现在你面前...",
            choices: [
                { text: "谨慎保守", effects: { hp: 0, money: -5, happiness: 5, career: -5, social: 0, family: 0, friends: 0, love: 0, loneliness: 0, freedom: -10, sanity: 0 } },
                { text: "大胆冒险", effects: { hp: -5, money: 15, happiness: 0, career: 10, social: -5, family: 0, friends: 0, love: 0, loneliness: 5, freedom: 10, sanity: 0 } },
                { text: "社交拓展", effects: { hp: 0, money: -10, happiness: 10, career: 0, social: 15, family: 0, friends: 10, love: 0, loneliness: -10, freedom: 0, sanity: 0 } }
            ]
        });
    }
}

function applyPassiveEffects() {
    const s = gameState.stats;

    // 金钱低 → 健康差
    if (s.money < 20) s.hp = Math.max(0, s.hp - 3);

    // 健康低 → 快乐差
    if (s.hp < 30) s.happiness = Math.max(0, s.happiness - 2);

    // 社交低 → 孤独高
    if (s.social < 20) s.loneliness = Math.min(100, s.loneliness + 3);

    // 孤独高 → 快乐低 + 精神差
    if (s.loneliness > 70) {
        s.happiness = Math.max(0, s.happiness - 3);
        s.sanity = Math.max(0, s.sanity - 2);
    }

    // 自由高 → 孤独高
    if (s.freedom > 80) s.loneliness = Math.min(100, s.loneliness + 2);

    // 家庭高 → 自由低
    if (s.family > 50) s.freedom = Math.max(0, s.freedom - 2);

    // 爱情高 → 快乐高
    if (s.love > 50) s.happiness = Math.min(100, s.happiness + 2);

    // 朋友高 → 孤独低 + 精神稳定
    if (s.friends > 50) {
        s.loneliness = Math.max(0, s.loneliness - 2);
        s.sanity = Math.min(100, s.sanity + 1);
    }

    // 快乐低 → 精神差
    if (s.happiness < 20) s.sanity = Math.max(0, s.sanity - 3);

    // 自杀风险检测
    if (s.loneliness > 80 && s.sanity < 30 && !gameState.isGameOver) {
        if (Math.random() < 0.3) {
            endGame("精神崩溃", "长期的孤独和绝望吞噬了你...你选择了离开这个世界");
            return;
        }
    }

    // 意外事件（健康>50时每年5%概率）
    if (s.hp > 50 && !gameState.isGameOver && Math.random() < 0.05) {
        const accidents = [
            { text: "严重的车祸", effects: { hp: -40, money: -20 } },
            { text: "高空坠物击中", effects: { hp: -30, money: -10 } },
            { text: "突发自然灾害", effects: { hp: -35, money: -25 } },
            { text: "严重的工业事故", effects: { hp: -45, career: -15 } },
            { text: "被人袭击", effects: { hp: -30, social: -10, sanity: -15 } }
        ];
        const accident = accidents[Math.floor(Math.random() * accidents.length)];
        for (const [key, val] of Object.entries(accident.effects)) {
            if (s[key] !== undefined) s[key] = Math.max(0, s[key] + val);
        }
        gameState.history.push(`⚠️ 意外：${accident.text}！`);
        addHistory(`⚠️ ${accident.text}`);
    }

    updateStats();
}

function displayEvent(data) {
    $("event-text").textContent = data.event;
    gameState.history.push(`[${gameState.age}岁] ${data.event}`);

    const container = $("choices-container");
    container.innerHTML = "";

    const choices = data.choices || [];
    choices.forEach((choice, index) => {
        const btn = document.createElement("button");
        btn.className = "choice-btn";
        const num = index + 1;
        btn.innerHTML = `<div class="choice-text">${num}. ${choice.text}</div>`;
        btn.onclick = () => makeChoice(choice);
        container.appendChild(btn);
    });
}

function formatEffects(effects) {
    if (!effects) return "";

    const labels = {
        hp: "💚健康", money: "💰金钱", happiness: "😊快乐", career: "📈事业",
        social: "🤝社交", family: "👨‍👩‍👧家庭", friends: "👯朋友", love: "💕爱情",
        loneliness: "🌙孤独", freedom: "🦅自由", sanity: "🧠精神"
    };

    const parts = [];
    for (const [key, value] of Object.entries(effects)) {
        if (value !== 0 && labels[key]) {
            const sign = value > 0 ? "+" : "";
            const color = value > 0 ? "#4ade80" : "#f87171";
            parts.push(`<span style="color:${color}">${labels[key]}${sign}${value}</span>`);
        }
    }
    return parts.length > 0 ? parts.join(" ") : "无变化";
}

function makeChoice(choice) {
    if (gameState.isGameOver) return;

    const effects = choice.effects;

    for (const [key, value] of Object.entries(effects)) {
        if (gameState.stats[key] !== undefined) {
            gameState.stats[key] = Math.max(0, Math.min(100, gameState.stats[key] + value));
        }
    }

    checkMilestones(choice.text);
    updateStats();
    gameState.history.push(`→ "${choice.text}"`);

    const container = $("choices-container");
    container.innerHTML = `<div class="choice-outcome"><span style="color:#888">选择了：</span>${choice.text}</div>`;

    $("continue-btn").classList.remove("hidden");

    checkGameOver();
}

function checkMilestones(choiceText) {
    const s = gameState.stats;

    if (s.love >= 80 && !gameState.milestones.includes("married")) {
        gameState.milestones.push("married");
        gameState.history.push("💍 你结婚了！");
    }
    if (s.family >= 70 && !gameState.milestones.includes("parent")) {
        gameState.milestones.push("parent");
        gameState.history.push("👶 你有了孩子！");
    }
    if (s.money >= 90 && !gameState.milestones.includes("rich")) {
        gameState.milestones.push("rich");
        gameState.history.push("💰 你实现了财务自由！");
    }
    if (s.sanity >= 90 && !gameState.milestones.includes("sane")) {
        gameState.milestones.push("sane");
        gameState.history.push("🧠 你保持了健全的精神");
    }
}

function updateStats() {
    const stats = ["hp", "money", "happiness", "career", "social", "family", "friends", "love", "loneliness", "freedom", "sanity"];

    stats.forEach(stat => {
        const val = gameState.stats[stat];
        const bar = $(`${stat}-bar`);
        const valEl = $(`${stat}-val`);

        if (bar) bar.style.width = `${val}%`;
        if (valEl) {
            valEl.textContent = val;
            if (val < 30) {
                valEl.style.color = val < 15 ? "#ef4444" : "#fbbf24";
            } else {
                valEl.style.color = "#eee";
            }
        }
    });
}

function checkGameOver() {
    const s = gameState.stats;

    if (s.hp <= 0) {
        endGame("健康耗尽", "长期积累的疾病最终夺走了你的生命");
    } else if (s.sanity <= 0) {
        endGame("精神崩溃", "你的精神最终不堪重负，选择了离开...");
    } else if (s.happiness <= 0 && s.social <= 0 && s.friends <= 0 && s.love <= 0 && s.family <= 0) {
        endGame("一无所有", "所有的快乐和羁绊都离你而去，你失去了活下去的意义...");
    }
}

function endGame(title, cause) {
    gameState.isGameOver = true;

    $("end-title").textContent = title;

    const s = gameState.stats;
    const score = Math.round(
        (s.hp + s.money + s.happiness + s.career + s.social +
         s.family + s.friends + s.love + (100 - s.loneliness) + s.freedom + s.sanity) / 11
    );

    const summary = generateSummary();

    $("end-stats").innerHTML = `
        <div class="score">🏆 人生评分: <strong>${score}</strong>/100</div>
        <div class="stats-grid-end">
            <div class="stat-item"><span>💚</span>${s.hp}</div>
            <div class="stat-item"><span>💰</span>${s.money}</div>
            <div class="stat-item"><span>😊</span>${s.happiness}</div>
            <div class="stat-item"><span>📈</span>${s.career}</div>
            <div class="stat-item"><span>🤝</span>${s.social}</div>
            <div class="stat-item"><span>👨‍👩‍👧</span>${s.family}</div>
            <div class="stat-item"><span>👯</span>${s.friends}</div>
            <div class="stat-item"><span>💕</span>${s.love}</div>
            <div class="stat-item"><span>🌙</span>${s.loneliness}</div>
            <div class="stat-item"><span>🦅</span>${s.freedom}</div>
            <div class="stat-item"><span>🧠</span>${s.sanity}</div>
        </div>
    `;

    const milestoneMap = {
        married: "💍 结婚", parent: "👶 为人父母", rich: "💰 财务自由", sane: "🧠 精神健全"
    };

    $("end-summary").innerHTML = `
        <p><strong>死因：</strong>${cause}</p>
        <p><strong>享年：</strong>${gameState.age}岁</p>
        <hr style="border-color:#333;margin:15px 0">
        <p><strong>人生轨迹：</strong></p>
        <p>${summary}</p>
        ${gameState.milestones.length > 0 ? `<p><strong>成就：</strong>${gameState.milestones.map(m => milestoneMap[m] || m).join(" ")}</p>` : ""}
    `;

    showScreen("end-screen");
}

function generateSummary() {
    const s = gameState.stats;
    const parts = [];

    if (s.money >= 80) parts.push("通过努力积累了财富");
    else if (s.money < 20) parts.push("一生为钱所困");

    if (s.career >= 70) parts.push("事业上有所成就");
    else if (s.career < 20) parts.push("事业上毫无起色");

    if (s.family >= 60) parts.push("拥有美满的家庭");
    else if (s.family < 10) parts.push("始终孑然一身");

    if (s.friends >= 60) parts.push("结识了很多朋友");
    else if (s.friends < 10) parts.push("身边没有知己");

    if (s.love >= 60) parts.push("拥有美好的爱情");
    else if (s.love < 10) parts.push("爱情一片空白");

    if (s.loneliness >= 70) parts.push("内心充满孤独");
    else if (s.loneliness < 30) parts.push("内心充实而温暖");

    if (s.freedom >= 70) parts.push("一生追求自由");
    else if (s.freedom < 30) parts.push("被责任和家庭束缚");

    if (s.sanity >= 70) parts.push("保持了健全的精神");
    else if (s.sanity < 30) parts.push("精神长期受创");

    return parts.length > 0 ? parts.join("；") : "平凡而真实的一生";
}

function toggleHistory() {
    $("history-panel").classList.toggle("hidden");
}

function addHistory(text) {
    const list = $("history-list");
    const li = document.createElement("li");
    li.textContent = text;
    list.insertBefore(li, list.firstChild);
}

function restartGame() {
    $("history-list").innerHTML = "";
    $("choices-container").innerHTML = "";
    $("continue-btn").classList.add("hidden");
    showScreen("start-screen");
}

function init() {
    showScreen("start-screen");
}

init();