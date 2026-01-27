const ADMIN_ID = 6643037038;
const BOT_TOKEN = token;
const API = `https://api.telegram.org/bot${BOT_TOKEN}`;

export default {
  async fetch(req, env) {
    if (req.method !== "POST") return new Response("OK");

    const update = await req.json();

    if (update.message) {
      return await handleMessage(update.message, env);
    }

    if (update.callback_query) {
      return await handleCallback(update.callback_query, env);
    }

    return new Response("OK");
  }
};

// =====================
// MESSAGE HANDLER
// =====================
async function handleMessage(msg, env) {
  const chatId = msg.chat.id;
  const userId = msg.from.id;
  const text = msg.text || "";

  // START
  if (text === "/start") {
    if (userId === ADMIN_ID) {
      await sendMessage(chatId,
        "Добро пожаловать, Админ!\nXush kelibsiz, Admin!",
        getAdminMainKb()
      );
      return ok();
    }

    await sendMessage(chatId,
      "Введите ваше имя:\nIsmingizni kiriting:"
    );

    await setState(env, userId, "waiting_name");
    return ok();
  }

  const state = await getState(env, userId);

  // NAME
  if (state === "waiting_name") {
    await saveTemp(env, userId, "name", text);

    await sendMessage(chatId,
      "Теперь отправьте номер телефона:\nEndi telefon raqamingizni yuboring:",
      getPhoneKb()
    );

    await setState(env, userId, "waiting_phone");
    return ok();
  }

  // PHONE
  if (state === "waiting_phone" && msg.contact) {
    await saveTemp(env, userId, "phone", msg.contact.phone_number);

    await sendMessage(chatId,
      "Введите ваш адрес:\nManzilingizni kiriting:"
    );

    await setState(env, userId, "waiting_address");
    return ok();
  }

  // ADDRESS → SAVE TO D1
  if (state === "waiting_address") {
    const temp = await getTemp(env, userId);

    await env.DB.prepare(`
      INSERT OR REPLACE INTO users (telegram_id, name, phone, address)
      VALUES (?, ?, ?, ?)
    `).bind(userId, temp.name, temp.phone, text).run();

    await clearTemp(env, userId);

    await sendMessage(chatId,
      "Регистрация завершена! ✅\nRo‘yxatdan o‘tish yakunlandi! ✅",
      { remove_keyboard: true }
    );
    return ok();
  }

  // USER → ADMIN
  if (userId !== ADMIN_ID && msg.chat.type === "private") {
    const { results } = await env.DB.prepare(
      "SELECT * FROM users WHERE telegram_id = ?"
    ).bind(userId).all();

    if (!results.length) {
      await sendMessage(chatId,
        "Сначала пройдите регистрацию: /start\nAvval ro‘yxatdan o‘ting: /start"
      );
      return ok();
    }

    const user = results[0];

    const header =
      `👤 **Имя / Ism:** ${user.name}\n` +
      `📞 **Телефон / Telefon:** \`${user.phone}\`\n` +
      `📍 **Адрес / Manzil:** ${user.address}\n` +
      `🆔 **ID:** \`${userId}\`\n` +
      `------------------------\n`;

    if (msg.photo) {
      const fileId = msg.photo[msg.photo.length - 1].file_id;
      await sendPhoto(ADMIN_ID, fileId, header + (msg.caption || ""), getAdminReplyKb(userId));
    } else {
      await sendMessage(ADMIN_ID, header + text, getAdminReplyKb(userId), "Markdown");
    }

    await sendMessage(chatId,
      "Сообщение отправлено админу ✅\nXabar adminga yuborildi ✅"
    );
    return ok();
  }

  // ADMIN REPLY MODE
  if (userId === ADMIN_ID) {
    const adminState = await getState(env, userId);
    if (adminState?.startsWith("reply_")) {
      const targetId = adminState.split("_")[1];

      await sendMessage(targetId,
        `✉️ **Ответ админа / Admin javobi:**\n\n${text}`,
        null,
        "Markdown"
      );

      await sendMessage(chatId, "Отправлено ✅ / Yuborildi ✅");
      await clearState(env, userId);
      return ok();
    }

    if (adminState === "broadcast") {
      const { results } = await env.DB.prepare("SELECT telegram_id FROM users").all();

      let count = 0;
      for (const u of results) {
        try {
          await sendMessage(u.telegram_id, text);
          count++;
        } catch {}
      }

      await sendMessage(chatId,
        `Рассылка завершена ✅\nYuborildi: ${count} ta`
      );
      await clearState(env, userId);
      return ok();
    }
  }

  return ok();
}

// =====================
// CALLBACK HANDLER
// =====================
async function handleCallback(cb, env) {
  const data = cb.data;
  const adminId = cb.from.id;

  // ADMIN REPLY BUTTON
  if (data.startsWith("reply_")) {
    const uid = data.split("_")[1];
    await setState(env, adminId, `reply_${uid}`);

    await sendMessage(adminId,
      `Введите ответ пользователю:\nFoydalanuvchiga javob yozing (ID: ${uid})`
    );

    await answerCallback(cb.id);
    return ok();
  }

  // BROADCAST BUTTON
  if (data === "broadcast") {
    await setState(env, adminId, "broadcast");

    await sendMessage(adminId,
      "Отправьте сообщение для рассылки:\nXabar yuboring (ommaviy):"
    );

    await answerCallback(cb.id);
    return ok();
  }

  return ok();
}

// =====================
// TELEGRAM HELPERS
// =====================
async function sendMessage(chatId, text, replyMarkup = null, parseMode = null) {
  return fetch(`${API}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text,
      parse_mode: parseMode,
      reply_markup: replyMarkup
    })
  });
}

async function sendPhoto(chatId, fileId, caption, replyMarkup = null) {
  return fetch(`${API}/sendPhoto`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      photo: fileId,
      caption,
      parse_mode: "Markdown",
      reply_markup: replyMarkup
    })
  });
}

async function answerCallback(id) {
  return fetch(`${API}/answerCallbackQuery`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ callback_query_id: id })
  });
}

// =====================
// KEYBOARDS
// =====================
function getPhoneKb() {
  return {
    keyboard: [[{ text: "📱 Отправить номер телефона / Telefon yuborish", request_contact: true }]],
    resize_keyboard: true,
    one_time_keyboard: true
  };
}

function getAdminReplyKb(userId) {
  return {
    inline_keyboard: [[{ text: "✉️ Ответить / Javob berish", callback_data: `reply_${userId}` }]]
  };
}

function getAdminMainKb() {
  return {
    inline_keyboard: [[{ text: "📢 Рассылка / Xabar yuborish", callback_data: "broadcast" }]]
  };
}

// =====================
// STATE STORAGE (D1)
// =====================
async function setState(env, userId, state) {
  await env.DB.prepare(`
    CREATE TABLE IF NOT EXISTS states (
      user_id TEXT PRIMARY KEY,
      state TEXT,
      temp TEXT
    )
  `).run();

  await env.DB.prepare(`
    INSERT OR REPLACE INTO states (user_id, state, temp)
    VALUES (?, ?, COALESCE((SELECT temp FROM states WHERE user_id = ?), '{}'))
  `).bind(userId, state, userId).run();
}

async function getState(env, userId) {
  const { results } = await env.DB.prepare(
    "SELECT state FROM states WHERE user_id = ?"
  ).bind(userId).all();
  return results[0]?.state || null;
}

async function saveTemp(env, userId, key, value) {
  const { results } = await env.DB.prepare(
    "SELECT temp FROM states WHERE user_id = ?"
  ).bind(userId).all();

  const temp = results.length ? JSON.parse(results[0].temp || "{}") : {};
  temp[key] = value;

  await env.DB.prepare(`
    INSERT OR REPLACE INTO states (user_id, state, temp)
    VALUES (?, COALESCE((SELECT state FROM states WHERE user_id = ?), NULL), ?)
  `).bind(userId, userId, JSON.stringify(temp)).run();
}

async function getTemp(env, userId) {
  const { results } = await env.DB.prepare(
    "SELECT temp FROM states WHERE user_id = ?"
  ).bind(userId).all();
  return results.length ? JSON.parse(results[0].temp || "{}") : {};
}

async function clearTemp(env, userId) {
  await env.DB.prepare("DELETE FROM states WHERE user_id = ?").bind(userId).run();
}

async function clearState(env, userId) {
  await env.DB.prepare("DELETE FROM states WHERE user_id = ?").bind(userId).run();
}

function ok() {
  return new Response("OK");
}
