// Modul ini menangani pratinjau gambar, drag-and-drop, dan nilai status aktif pada form menu.
(function () {
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const input = document.getElementById("imageInput");
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const box = document.querySelector("[data-upload-box]");
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const preview = document.querySelector("[data-upload-preview]");
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const placeholder = document.querySelector("[data-upload-placeholder]");
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const statusToggle = document.getElementById("statusToggle");
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const statusValue = document.getElementById("isActiveValue");

    // File diperiksa jenis dan ukurannya sebelum dibaca sebagai pratinjau di browser.
    function showPreview(file) {
        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (!file || !preview || !placeholder) return;

        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const allowedTypes = ["image/png", "image/jpeg", "image/jpg", "image/webp"];
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const maxSize = 5 * 1024 * 1024;

        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (!allowedTypes.includes(file.type)) {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            alert("Format gambar tidak valid. Gunakan PNG, JPG, JPEG, atau WEBP.");
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            input.value = "";
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            return;
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (file.size > maxSize) {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            alert("Ukuran gambar maksimal 5MB.");
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            input.value = "";
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            return;
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const reader = new FileReader();
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        reader.onload = function (event) {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            preview.src = event.target.result;
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            preview.hidden = false;
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            placeholder.hidden = true;
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (box) box.classList.add("has-image");
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        };
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        reader.readAsDataURL(file);
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
    if (input) {
        // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
        input.addEventListener("change", function () {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            showPreview(this.files && this.files[0]);
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
    if (box) {
        // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
        ["dragenter", "dragover"].forEach(function (eventName) {
            // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
            box.addEventListener(eventName, function (event) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                event.preventDefault();
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                box.classList.add("is-dragging");
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });

        // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
        ["dragleave", "drop"].forEach(function (eventName) {
            // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
            box.addEventListener(eventName, function (event) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                event.preventDefault();
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                box.classList.remove("is-dragging");
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });

        // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
        box.addEventListener("drop", function (event) {
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const file = event.dataTransfer.files && event.dataTransfer.files[0];
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (!file || !input) return;

            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const dataTransfer = new DataTransfer();
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            dataTransfer.items.add(file);
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            input.files = dataTransfer.files;
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            showPreview(file);
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Toggle visual selalu disinkronkan dengan input tersembunyi yang dikirim melalui form.
    if (statusToggle && statusValue) {
        // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
        statusToggle.addEventListener("click", function () {
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const nextState = !statusToggle.classList.contains("is-on");
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            statusToggle.classList.toggle("is-on", nextState);
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            statusToggle.setAttribute("aria-pressed", String(nextState));
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            statusValue.value = nextState ? "1" : "0";
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }
// Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
})();
