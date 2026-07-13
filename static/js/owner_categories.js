// Modul mandiri ini mengendalikan modal tambah/edit dan validasi awal nama kategori.
(function () {
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const modal = document.querySelector("[data-category-modal]");
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const form = document.querySelector("[data-category-form]");
    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
    if (!modal || !form) return;

    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const title = document.getElementById("categoryModalTitle");
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const nameInput = document.querySelector("[data-category-name]");
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const descriptionInput = document.querySelector("[data-category-description]");
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const submitButton = document.querySelector("[data-category-submit]");
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const openButtons = document.querySelectorAll("[data-open-category-modal]");
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const closeButtons = document.querySelectorAll("[data-close-category-modal]");
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const createAction = form.dataset.createAction;
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const editActionTemplate = form.dataset.editActionTemplate;
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    let currentId = form.dataset.currentId || "";

    // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
    function normalizeName(value) {
        // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
        return String(value || "").trim().replace(/\s+/g, " ");
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
    function nameKey(value) {
        // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
        return normalizeName(value).toLowerCase();
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
    function categoryNames() {
        // Map mengubah setiap elemen menjadi bentuk data yang diperlukan berikutnya.
        return Array.from(document.querySelectorAll("[data-open-category-modal][data-id]")).map(function (button) {
            // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
            return {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                id: String(button.dataset.id || ""),
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                name: button.dataset.name || "",
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            };
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
    function setFieldError(message) {
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        let error = form.querySelector(".field-error");
        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (!message) {
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (error) error.remove();
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            return;
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (!error) {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            error = document.createElement("small");
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            error.className = "field-error";
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            nameInput.insertAdjacentElement("afterend", error);
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        error.textContent = message;
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Mode menentukan action form serta data awal yang ditampilkan pada modal.
    function openModal(mode, data) {
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        currentId = data && data.id ? String(data.id) : "";
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        form.dataset.currentId = currentId;
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        form.action = mode === "edit"
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            ? editActionTemplate.replace("/0/", "/" + currentId + "/")
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            : createAction;

        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (title) title.textContent = mode === "edit" ? "Edit Category" : "Add Category";
        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (submitButton) submitButton.textContent = mode === "edit" ? "Simpan Perubahan" : "Simpan Kategori";
        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (nameInput) nameInput.value = data && data.name ? data.name : "";
        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (descriptionInput) descriptionInput.value = data && data.description ? data.description : "";

        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        setFieldError("");
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        modal.hidden = false;
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        window.setTimeout(function () {
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (nameInput) nameInput.focus();
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }, 0);
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
    function closeModal() {
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        modal.hidden = true;
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        form.classList.remove("is-loading");
        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (submitButton) submitButton.disabled = false;
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
    openButtons.forEach(function (button) {
        // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
        button.addEventListener("click", function () {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            openModal(button.dataset.mode || "create", button.dataset);
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    });

    // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
    closeButtons.forEach(function (button) {
        // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
        button.addEventListener("click", closeModal);
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    });

    // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
    document.addEventListener("keydown", function (event) {
        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (event.key === "Escape" && !modal.hidden) {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            closeModal();
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    });

    // Validasi browser mencegah nama kosong atau duplikat sebelum form dikirim ke Flask.
    form.addEventListener("submit", function (event) {
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const cleanName = normalizeName(nameInput && nameInput.value);
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const duplicate = categoryNames().some(function (category) {
            // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
            return category.id !== String(currentId || "") && nameKey(category.name) === nameKey(cleanName);
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });

        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (!cleanName) {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            event.preventDefault();
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            setFieldError("Nama kategori wajib diisi.");
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (nameInput) nameInput.focus();
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            return;
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (duplicate) {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            event.preventDefault();
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            setFieldError("Nama kategori sudah digunakan.");
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (nameInput) nameInput.focus();
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            return;
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        nameInput.value = cleanName;
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        form.classList.add("is-loading");
        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (submitButton) submitButton.disabled = true;
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    });
// Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
})();
