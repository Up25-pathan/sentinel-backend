const puter = require('@heyputer/puter.js');

async function test() {
    try {
        console.log("Testing puter.ai.chat()");
        const response = await puter.ai.chat("Reply with exactly: OK");
        console.log("Response:", response);
    } catch (err) {
        console.error("Error:", err);
    }
}

test();
