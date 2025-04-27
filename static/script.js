document.addEventListener("DOMContentLoaded", function () {
    const pathParts = window.location.pathname.split("/");
    const isBookingPage = pathParts[1] === "book" && pathParts.length >= 4;
    const isReleasePage = pathParts[1] === "release" && pathParts.length >= 4;

    const blockCoordinates = {
        techpark: { lat: 12.823069, lng: 80.044892 },
        medical: { lat: 12.821226, lng: 80.047711 },
        fablab: { lat: 12.822768, lng: 80.044804 },
        mba: { lat: 12.824227, lng: 80.043195 },
        dental: { lat: 12.825665, lng: 80.047410 }
    };

    initToast(); // Initialize toast container

    if (isBookingPage) {
        const block = pathParts[2];
        const slot = pathParts[3];
        launchBookingFlow(block, slot);
    } else if (isReleasePage) {
        const block = pathParts[2];
        const slot = pathParts[3];
        launchReleaseFlow(block, slot);
    } else {
        const blockSelect = document.getElementById("block-select");
        fetchSlots(blockSelect.value);
        blockSelect.addEventListener("change", () => {
            fetchSlots(blockSelect.value);
        });
    }

    function fetchSlots(block) {
        fetch(`/status/${block}`)
            .then(response => response.json())
            .then(data => {
                const container = document.getElementById("parking-slots");
                container.innerHTML = "";
                Object.keys(data).forEach(slot => {
                    const div = document.createElement("div");
                    div.classList.add("slot", data[slot].status);
                    div.textContent = `Slot ${slot}`;
                    div.onclick = () => handleSlotClick(block, slot, data[slot]);
                    container.appendChild(div);
                });
            });
    }

    function handleSlotClick(block, slot, slotData) {
        resetUI();

        const allSlots = document.querySelectorAll(".slot");
        allSlots.forEach(s => s.classList.remove("selected"));
        const clickedSlot = Array.from(allSlots).find(s => s.textContent.trim() === `Slot ${slot}`);
        if (clickedSlot) clickedSlot.classList.add("selected");

        const isReleasePage = window.location.pathname.includes('release');

        if (slotData.status === "available") {
            showBookingQRCode(block, slot);
        } else {
            if (isReleasePage) {
                document.getElementById("otp-container").style.display = "block";

                const btn = document.getElementById("send-otp-button");
                const newBtn = btn.cloneNode(true);
                btn.parentNode.replaceChild(newBtn, btn);
                newBtn.addEventListener("click", () => sendReleaseOTP(block, slot));

                const verifyBtn = document.getElementById("verify-otp-button");
                const newVerifyBtn = verifyBtn.cloneNode(true);
                verifyBtn.parentNode.replaceChild(newVerifyBtn, verifyBtn);
                newVerifyBtn.addEventListener("click", () => {
                    const phone = document.getElementById("phone-number").value.trim();
                    verifyReleaseOTP(phone, block, slot);
                });

            } else {
                window.location.href = `/release/${block}/${slot}`;
            }
        }
    }

    function showBookingQRCode(block, slot) {
        getDeviceInfo().then(deviceInfo => {
            fetch(`/generate_qr/${block}/${slot}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ device_info: deviceInfo })
            })
                .then(response => response.json())
                .then(data => {
                    if (data.qr_code) {
                        displayQRCode(data.qr_code, "Scan this QR to proceed with booking", block);
                    }
                });
        });
    }

    function displayQRCode(qrCode, message, block = null) {
        document.getElementById("qr-message").textContent = message;
        document.getElementById("qr-code").src = "data:image/png;base64," + qrCode;
        document.getElementById("qr-code-container").style.display = "block";

        const blockLabel = document.getElementById("block-name");
        if (blockLabel && block) {
            blockLabel.textContent = `Block: ${block.charAt(0).toUpperCase() + block.slice(1)}`;
            blockLabel.style.display = "block";
        }

        const mapBtn = document.getElementById("map-button");
        if (block && blockCoordinates[block]) {
            const { lat, lng } = blockCoordinates[block];
            mapBtn.href = `https://www.google.com/maps?q=${lat},${lng}`;
            mapBtn.textContent = "Navigate to Parking";
            mapBtn.style.display = "inline-block";
            mapBtn.className = "map-button";
        } else {
            mapBtn.style.display = "none";
        }
    }

    function sendOTP(block, slot) {
        const phone = document.getElementById("phone-number").value.trim();
        if (!phone) return toast("Please enter a phone number");

        fetch(`/send_otp/${block}/${slot}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone_number: phone })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.getElementById("otp-phone-input").style.display = "none";
                    document.getElementById("otp-verification").style.display = "block";
                    document.getElementById("otp-message").textContent = "OTP sent to your number.";
                    document.getElementById("masked-number").textContent = `****${phone.slice(-4)}`;
                    document.getElementById("otp-phone-hint").style.display = "block";

                    const verifyBtn = document.getElementById("verify-otp-button");
                    const newVerifyBtn = verifyBtn.cloneNode(true);
                    verifyBtn.parentNode.replaceChild(newVerifyBtn, verifyBtn);
                    newVerifyBtn.addEventListener("click", () => verifyOTP(phone, block, slot));
                } else {
                    toast("Failed to send OTP.");
                }
            });
    }

    function verifyOTP(phone, block, slot) {
        const otp = document.getElementById("otp").value.trim();
        if (!otp) return toast("Please enter the OTP");

        fetch("/verify_otp", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone_number: phone, otp: otp, block, slot })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    toast("✅ Booking confirmed");
                    toast("✅ COOKIES SAVED");
                    resetUI();
                    fetchSlots(block);

                    fetch(`/booking_qr/${block}/${slot}`)
                        .then(res => res.json())
                        .then(qr => {
                            if (qr.qr_code) {
                                const a = document.createElement("a");
                                a.href = "data:image/png;base64," + qr.qr_code;
                                a.download = `booking_qr_${block}_${slot}.png`;
                                document.body.appendChild(a);
                                a.click();
                                document.body.removeChild(a);
                                showOneTimeQRPopup(); // ✅ Popup triggered after download
                            }
                        });

                } else {
                    toast(data.message || "Invalid OTP");
                }
            });
    }

    function verifyReleaseOTP(phone, block, slot) {
        const otp = document.getElementById("otp").value.trim();
        if (!otp) return toast("Please enter the OTP");

        fetch("/verify_release_otp", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone_number: phone, otp: otp, block, slot })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    toast("✅ Slot successfully released");
                    resetUI();
                    fetchSlots(block);

                    fetch(`/release_qr/${block}/${slot}`)
                        .then(res => res.json())
                        .then(qr => {
                            if (qr.qr_code) {
                                const a = document.createElement("a");
                                a.href = "data:image/png;base64," + qr.qr_code;
                                a.download = `release_qr_${block}_${slot}.png`;
                                document.body.appendChild(a);
                                a.click();
                                document.body.removeChild(a);
                                showOneTimeQRPopup(); // ✅ Popup triggered after download
                            }
                        });
                } else {
                    toast(data.message || "Invalid OTP");
                }
            });
    }

    function resetUI() {
        document.getElementById("qr-code-container").style.display = "none";
        document.getElementById("otp-container").style.display = "none";
        document.getElementById("otp-phone-input").style.display = "block";
        document.getElementById("otp-verification").style.display = "none";
        document.getElementById("otp-message").textContent = "";
        document.getElementById("phone-number").value = "";
        document.getElementById("otp").value = "";
        document.getElementById("map-button").style.display = "none";
        document.getElementById("otp-phone-hint").style.display = "none";

        const blockLabel = document.getElementById("block-name");
        if (blockLabel) blockLabel.style.display = "none";

        const allSlots = document.querySelectorAll(".slot");
        allSlots.forEach(s => s.classList.remove("selected"));
    }

    function getDeviceInfo() {
        return Promise.resolve({
            userAgent: navigator.userAgent,
            screenWidth: screen.width,
            screenHeight: screen.height,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        });
    }

    function launchBookingFlow(block, slot) {
        resetUI();
        document.getElementById("otp-container").style.display = "block";

        const btn = document.getElementById("send-otp-button");
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);
        newBtn.addEventListener("click", () => sendOTP(block, slot));
    }

    function launchReleaseFlow(block, slot) {
        resetUI();
        document.getElementById("otp-container").style.display = "block";

        const btn = document.getElementById("send-otp-button");
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);
        newBtn.addEventListener("click", () => sendReleaseOTP(block, slot));

        const verifyBtn = document.getElementById("verify-otp-button");
        const newVerifyBtn = verifyBtn.cloneNode(true);
        verifyBtn.parentNode.replaceChild(newVerifyBtn, verifyBtn);
        newVerifyBtn.addEventListener("click", () => {
            const phone = document.getElementById("phone-number").value.trim();
            verifyReleaseOTP(phone, block, slot);
        });
    }

    function sendReleaseOTP(block, slot) {
        const phone = document.getElementById("phone-number").value.trim();
        if (!phone) return toast("Please enter a phone number");

        fetch(`/send_release_otp/${block}/${slot}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone_number: phone })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.getElementById("otp-phone-input").style.display = "none";
                    document.getElementById("otp-verification").style.display = "block";
                    document.getElementById("otp-message").textContent = "OTP sent to your number.";
                    document.getElementById("masked-number").textContent = `****${phone.slice(-4)}`;
                    document.getElementById("otp-phone-hint").style.display = "block";
                } else {
                    toast(data.message || "Failed to send release OTP.");
                }
            });
    }

    // 🧁 Toast notification system
    function initToast() {
        const toastContainer = document.createElement("div");
        toastContainer.id = "toast-container";
        toastContainer.style.position = "fixed";
        toastContainer.style.bottom = "20px";
        toastContainer.style.right = "20px";
        toastContainer.style.zIndex = "9999";
        document.body.appendChild(toastContainer);
    }

    function toast(message, duration = 3000) {
        const toast = document.createElement("div");
        toast.textContent = message;
        toast.style.background = "#323232";
        toast.style.color = "white";
        toast.style.padding = "10px 16px";
        toast.style.marginTop = "10px";
        toast.style.borderRadius = "8px";
        toast.style.boxShadow = "0 4px 6px rgba(0,0,0,0.1)";
        toast.style.fontSize = "14px";
        toast.style.opacity = "0.95";

        document.getElementById("toast-container").appendChild(toast);
        setTimeout(() => toast.remove(), duration);
    }

    function showOneTimeQRPopup() {
        const seenPopup = document.cookie.split('; ').find(row => row.startsWith('qrSaved='));
        if (!seenPopup) {
            toast("📥 QR Code auto-downloaded. Check your downloads folder!");
            document.cookie = "qrSaved=true; path=/; max-age=86400"; // 1 day
        }
    }
});
