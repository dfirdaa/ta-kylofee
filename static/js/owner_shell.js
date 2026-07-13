// Modul sidebar owner menyimpan keadaan desktop dan mengatur perilaku panel pada layar kecil.
(function () {
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const page = document.querySelector(".owner-page");
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const sidebar = document.querySelector("[data-owner-sidebar]");
    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
    if (!page || !sidebar) return;

    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const stateKey = "kyloffee_owner_sidebar_collapsed";
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const mobileQuery = window.matchMedia("(max-width: 760px)");
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const toggleButtons = document.querySelectorAll("[data-owner-sidebar-toggle]");
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const overlay = document.querySelector("[data-owner-sidebar-overlay]");

    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    let collapsed = localStorage.getItem(stateKey) === "1";
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    let mobileOpen = false;

    // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
    function setToggleLabels() {
        // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
        toggleButtons.forEach(function (button) {
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const expanded = mobileQuery.matches ? mobileOpen : !collapsed;
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            button.setAttribute("aria-expanded", String(expanded));
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            button.setAttribute(
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                "aria-label",
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                mobileQuery.matches
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    ? (mobileOpen ? "Tutup sidebar Owner" : "Buka sidebar Owner")
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    : (collapsed ? "Perbesar sidebar Owner" : "Perkecil sidebar Owner")
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            );
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Menerapkan class tampilan, overlay, aksesibilitas, dan penyimpanan state secara bersamaan.
    function applyState(options) {
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const shouldPersist = !options || options.persist !== false;
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        page.classList.toggle("owner-sidebar-collapsed", collapsed && !mobileQuery.matches);
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        page.classList.toggle("owner-sidebar-open", mobileOpen && mobileQuery.matches);
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        sidebar.classList.toggle("owner-sidebar--collapsed", collapsed && !mobileQuery.matches);

        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (overlay) {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            overlay.hidden = !(mobileOpen && mobileQuery.matches);
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (shouldPersist && !mobileQuery.matches) {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            localStorage.setItem(stateKey, collapsed ? "1" : "0");
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        setToggleLabels();
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
    toggleButtons.forEach(function (button) {
        // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
        button.addEventListener("click", function () {
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (mobileQuery.matches) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                mobileOpen = !mobileOpen;
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            } else {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                collapsed = !collapsed;
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            applyState();
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    });

    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
    if (overlay) {
        // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
        overlay.addEventListener("click", function () {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            mobileOpen = false;
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            applyState({ persist: false });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
    function handleViewportChange() {
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        mobileOpen = false;
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        applyState({ persist: false });
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
    if (mobileQuery.addEventListener) {
        // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
        mobileQuery.addEventListener("change", handleViewportChange);
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    } else if (mobileQuery.addListener) {
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        mobileQuery.addListener(handleViewportChange);
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
    document.addEventListener("keydown", function (event) {
        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (event.key === "Escape" && mobileOpen) {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            mobileOpen = false;
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            applyState({ persist: false });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    });

    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
    applyState({ persist: false });
// Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
})();
