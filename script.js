document.getElementById("toggle-mode").addEventListener("click", function() {
    document.body.classList.toggle("dark-mode");
    document.body.classList.toggle("light-mode");
});

document.getElementById("clear-chat").addEventListener("click", function() {
    document.getElementById("chat-box").innerHTML = "";
});

document.getElementById("chat-form").addEventListener("submit", function(e) {
    e.preventDefault();
    const userInput = document.getElementById("user-input").value;
    const topic = document.getElementById("topic").value;
    const chatBox = document.getElementById("chat-box");

    chatBox.innerHTML += `<div><b>You:</b> ${userInput}</div>`;
    document.getElementById("user-input").value = "";

    document.getElementById("typing").style.display = "block";

    fetch("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded"
        },
        body: `message=${encodeURIComponent(userInput)}&topic=${encodeURIComponent(topic)}`
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById("typing").style.display = "none";
        chatBox.innerHTML += `<div><b>Bot:</b> ${data.reply}</div>`;
        chatBox.scrollTop = chatBox.scrollHeight;
    });
});
<script>
    function toggleDarkMode() {
        document.body.classList.toggle("dark-mode");
    }
</script>

