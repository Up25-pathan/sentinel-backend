const Groq = require('groq-sdk');
require('dotenv').config({ path: './.env' });

async function testGroq() {
    try {
        console.log("Testing Groq API...");
        const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

        const response = await groq.chat.completions.create({
            model: 'llama3-8b-8192',
            messages: [{ role: 'user', content: 'Say strictly the word: OK' }],
            temperature: 0.1,
            max_tokens: 10
        });

        console.log("✅ Success! Groq responded:", response.choices[0].message.content);
    } catch (err) {
        console.error("❌ Groq Test Failed:", err.message);
    }
}

testGroq();
