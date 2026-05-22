document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("userForm");

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const name  = document.getElementById("input-name").value;
        const email = document.getElementById("input-email").value;
        const payload = {
            id: Date.now(),
            name:  name,
            email: email
        };

        document.getElementById("output").textContent = "Sending...";

        try {
            const response = await fetch("http://localhost:2026/info", {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                body:    JSON.stringify(payload)   
            });

            const result = await response.json();

            const userData = result.data;

            if (userData.name) {
                document.getElementById("cv-name").textContent = userData.name;
            }
            if (result.email) {
                document.getElementById("cv-email").textContent = "Email: " + userData.email;
            }

            document.getElementById("output").textContent =
                JSON.stringify(result, null, 2);

        } catch (error) {
            document.getElementById("output").textContent = "Error: " + error.message;
        }
    });
});