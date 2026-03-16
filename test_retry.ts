import axios from 'axios';

async function testRetry() {
    console.log("Starting retry test...");
    try {
        const response = await axios.post("http://localhost:3000/v1/chat/completions", {
            model: "doubao-lite-4k",
            messages: [{ role: "user", content: "Hello" }],
            stream: false
        }, {
            headers: {
                // By passing a token we know will fail, we can try to trigger a retry loop or standard error
                // We'll just pass a fake 'pooled' token to force the system to acquire from the pool,
                // and we'll watch the server logs to see what happens.
                "Authorization": "Bearer pooled"
            }
        });
        console.log("Response:", response.data);
    } catch (e: any) {
        console.error("Test failed as expected or unexpectedly:", e.response?.data || e.message);
    }
}

testRetry();
