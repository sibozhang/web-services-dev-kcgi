document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("userForm");

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const payload = {
            name: document.getElementById("input-name").value,
            email: document.getElementById("input-email").value,
            phone: document.getElementById("input-phone").value
        };

        const outputArea = document.getElementById("output");
        outputArea.textContent = "Sending to database...";

        try {
            const response = await fetch("http://localhost:2026/info", {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                body:    JSON.stringify(payload)   
            });

            const result = await response.json();
            outputArea.textContent = JSON.stringify(result, null, 4);

        } catch (error) {
            outputArea.textContent = "Error: " + error.message;
        }
    });
});