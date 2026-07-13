// Menunggu seluruh HTML siap sebelum memasang interaksi password, POS, keranjang, dan pembayaran.
document.addEventListener("DOMContentLoaded", function () {
    // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
    document.querySelectorAll("[data-toggle-password]").forEach(function (button) {
        // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
        button.addEventListener("click", function () {
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const targetId = button.getAttribute("data-toggle-password");
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const input = document.getElementById(targetId);
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (!input) return;

            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const isPassword = input.type === "password";
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            input.type = isPassword ? "text" : "password";
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            button.classList.toggle("is-visible", isPassword);
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            button.setAttribute("aria-label", isPassword ? "Sembunyikan password" : "Lihat password");
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    });

    // Kunci penyimpanan menjaga isi keranjang dan keadaan sidebar selama pengguna berpindah halaman.
    const stateKey = "kyloffee_pos_cart_v2";
    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const sidebarStateKey = "kyloffee_pos_sidebar_open";

    // Membaca state dengan try/catch agar data sessionStorage yang rusak tidak menghentikan halaman.
    function readState() {
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        try {
            // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
            return JSON.parse(sessionStorage.getItem(stateKey) || "{}") || {};
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        } catch (error) {
            // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
            return {};
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
    function writeState(nextState) {
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        sessionStorage.setItem(stateKey, JSON.stringify(nextState || {}));
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
    function clearState() {
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        sessionStorage.removeItem(stateKey);
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Menormalkan item keranjang supaya ID, harga, stok, dan jumlah selalu berupa angka yang aman dihitung.
    function normalizeItems(items) {
        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (!Array.isArray(items)) return [];
        // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
        return items
            // Map mengubah setiap elemen menjadi bentuk data yang diperlukan berikutnya.
            .map(function (item) {
                // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
                return {
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    id: Number(item.id || item.menu_id || 0),
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    name: String(item.name || "Menu"),
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    price: Math.max(0, Number(item.price || 0) || 0),
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    stock: Math.max(0, Number(item.stock || 0) || 0),
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    quantity: Math.max(1, Number(item.quantity || 1) || 1),
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                };
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            })
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            .filter(function (item) {
                // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
                return item.id > 0 && item.quantity > 0;
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
    function formatCurrency(amount) {
        // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
        return "Rp" + Math.max(0, Math.round(Number(amount) || 0)).toLocaleString("id-ID");
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
    function parseAmount(input) {
        // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
        return Math.max(0, Number(input && input.value ? input.value : 0) || 0);
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
    function escapeHtml(value) {
        // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
        return String(value).replace(/[&<>"']/g, function (char) {
            // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
            return {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                "&": "&amp;",
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                "<": "&lt;",
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                ">": "&gt;",
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                '"': "&quot;",
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                "'": "&#039;",
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }[char];
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
    function setTextAll(nodes, text) {
        // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
        nodes.forEach(function (node) {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            node.textContent = text;
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
    function normalizeFilterValue(value) {
        // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
        return String(value || "").trim().replace(/\s+/g, " ").toLowerCase();
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Menghitung jumlah item, subtotal, diskon, dan total yang dipakai POS serta halaman pembayaran.
    function calculateTotals(items, discount) {
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const subtotal = items.reduce(function (sum, item) {
            // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
            return sum + item.price * item.quantity;
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }, 0);
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const itemCount = items.reduce(function (sum, item) {
            // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
            return sum + item.quantity;
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }, 0);
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const discountAmount = Math.max(0, Number(discount || 0) || 0);
        // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
        return {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            subtotal,
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            itemCount,
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            discount: discountAmount,
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            total: Math.max(0, subtotal - discountAmount),
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        };
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
    function showMessage(box, text, tone) {
        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (!box) return;
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        box.hidden = false;
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        box.textContent = text;
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        box.className = "pos-message pos-message--" + tone;
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
    function clearMessage(box) {
        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (!box) return;
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        box.hidden = true;
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        box.textContent = "";
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        box.className = "pos-message";
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
    function readSidebarState() {
        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (window.matchMedia("(max-width: 760px)").matches) return false;
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const saved = localStorage.getItem(sidebarStateKey);
        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (saved === "0") return false;
        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (saved === "1") return true;
        // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
        return true;
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Mengaktifkan pencarian menu, filter kategori, sidebar, dan operasi keranjang pada halaman POS.
    function initPosPage(root) {
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const cart = new Map();
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const storedState = readState();
        // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
        normalizeItems(storedState.items).forEach(function (item) {
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const matchingCard = root.querySelector('[data-product-card][data-menu-id="' + item.id + '"]');
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (matchingCard) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                item.stock = Math.max(0, Number(matchingCard.dataset.stock || item.stock || 0) || 0);
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                item.name = matchingCard.dataset.name || item.name;
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                item.price = Math.max(0, Number(matchingCard.dataset.price || item.price || 0) || 0);
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (item.stock > 0) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                item.quantity = Math.min(item.quantity, item.stock);
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                cart.set(item.id, item);
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });

        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        let selectedCategory = "all";
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const paymentUrl = root.dataset.paymentUrl || "/pos/payment";
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const cartItems = root.querySelector("[data-cart-items]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const cartEmpty = root.querySelector("[data-cart-empty]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const cartCountLabels = root.querySelectorAll("[data-cart-count]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const menuSearchInput = root.querySelector("[data-menu-search]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const openPaymentButton = root.querySelector("[data-open-payment]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const messageBox = root.querySelector("[data-pos-message]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const summarySubtotalLabels = root.querySelectorAll("[data-summary-subtotal]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const summaryTotalLabels = root.querySelectorAll("[data-summary-total]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const productCards = Array.from(root.querySelectorAll("[data-product-card]"));
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const menuEmpty = root.querySelector("[data-menu-empty]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const sidebar = root.querySelector("[data-pos-sidebar]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const sidebarNavLinks = root.querySelectorAll(".pos-sidebar-nav-link");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const sidebarLogout = root.querySelector(".pos-sidebar-logout");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const sidebarToggleButtons = root.querySelectorAll("[data-pos-sidebar-toggle]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const mobileSidebarQuery = window.matchMedia("(max-width: 760px)");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        let isSidebarOpen = readSidebarState();

        // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
        function setSidebarOpen(nextState, options) {
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const shouldPersist = !options || options.persist !== false;
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const isMobileLayout = mobileSidebarQuery.matches;
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            isSidebarOpen = Boolean(nextState);
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            root.classList.toggle("is-sidebar-collapsed", !isSidebarOpen);
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            root.classList.toggle("is-sidebar-open", isSidebarOpen);
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            root.dataset.sidebarState = isSidebarOpen ? "expanded" : "collapsed";

            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (sidebar) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                sidebar.classList.toggle("pos-sidebar-mock--expanded", isSidebarOpen);
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                sidebar.classList.toggle("pos-sidebar-mock--collapsed", !isSidebarOpen);
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }

            // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
            sidebarNavLinks.forEach(function (link) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                link.classList.toggle("pos-sidebar-nav-link--expanded", isSidebarOpen);
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                link.classList.toggle("pos-sidebar-nav-link--collapsed", !isSidebarOpen);
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });

            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (sidebarLogout) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                sidebarLogout.classList.toggle("pos-sidebar-logout--expanded", isSidebarOpen);
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                sidebarLogout.classList.toggle("pos-sidebar-logout--collapsed", !isSidebarOpen);
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }

            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (shouldPersist && !isMobileLayout) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                localStorage.setItem(sidebarStateKey, isSidebarOpen ? "1" : "0");
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }

            // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
            sidebarToggleButtons.forEach(function (button) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                button.setAttribute("aria-expanded", String(isSidebarOpen));
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                button.setAttribute("aria-label", isSidebarOpen ? "Tutup sidebar POS" : "Buka sidebar POS");
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
        sidebarToggleButtons.forEach(function (button) {
            // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
            button.addEventListener("click", function () {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                setSidebarOpen(!isSidebarOpen);
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });

        // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
        function handleSidebarViewportChange(event) {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            setSidebarOpen(event.matches ? false : readSidebarState(), { persist: false });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
        if (mobileSidebarQuery.addEventListener) {
            // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
            mobileSidebarQuery.addEventListener("change", handleSidebarViewportChange);
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        } else if (mobileSidebarQuery.addListener) {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            mobileSidebarQuery.addListener(handleSidebarViewportChange);
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
        root.addEventListener("click", function (event) {
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (mobileSidebarQuery.matches && isSidebarOpen && event.target === root) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                setSidebarOpen(false);
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });

        // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
        function currentItems() {
            // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
            return Array.from(cart.values());
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
        function persistState() {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            writeState({
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                ...readState(),
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                items: currentItems(),
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Produk hanya ditampilkan bila cocok dengan kategori aktif dan kata pencarian pengguna.
        function filterProducts() {
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const keyword = normalizeFilterValue(menuSearchInput && menuSearchInput.value ? menuSearchInput.value : "");
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            let visibleCount = 0;

            // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
            productCards.forEach(function (card) {
                // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
                const category = normalizeFilterValue(card.dataset.category || "");
                // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
                const searchableText = [
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    card.dataset.name || "",
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    card.dataset.category || "",
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    card.dataset.description || "",
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                ].join(" ").toLowerCase().replace(/\s+/g, " ");
                // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
                const matchesCategory = selectedCategory === "all" || category === selectedCategory;
                // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
                const matchesSearch = !keyword || searchableText.includes(keyword);
                // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
                const isVisible = matchesCategory && matchesSearch;

                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                card.hidden = !isVisible;
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                card.classList.toggle("is-hidden", !isVisible);
                // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                if (isVisible) visibleCount += 1;
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });

            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (menuEmpty) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                menuEmpty.hidden = productCards.length === 0 || visibleCount > 0;
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Merender ulang keranjang dan total setiap kali jumlah item berubah.
        function renderCart() {
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const items = currentItems();
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const totals = calculateTotals(items, 0);

            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (cartEmpty) cartEmpty.hidden = items.length > 0;
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            setTextAll(cartCountLabels, totals.itemCount + (totals.itemCount === 1 ? " Item" : " Items"));
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            setTextAll(summarySubtotalLabels, formatCurrency(totals.subtotal));
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            setTextAll(summaryTotalLabels, formatCurrency(totals.subtotal));

            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (openPaymentButton) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                openPaymentButton.disabled = items.length === 0 || totals.subtotal <= 0;
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }

            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (cartItems) {
                // Map mengubah setiap elemen menjadi bentuk data yang diperlukan berikutnya.
                cartItems.innerHTML = items.map(function (item) {
                    // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
                    return [
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        '<article class="pos-cart-item">',
                            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                            '<div>',
                                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                                '<strong>' + escapeHtml(item.name) + '</strong>',
                                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                                '<small>' + formatCurrency(item.price) + ' / item</small>',
                            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                            '</div>',
                            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                            '<div class="cart-qty-control">',
                                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                                '<button type="button" data-cart-action="minus" data-menu-id="' + item.id + '">-</button>',
                                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                                '<span>' + item.quantity + '</span>',
                                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                                '<button type="button" data-cart-action="plus" data-menu-id="' + item.id + '" ' + (item.quantity >= item.stock ? "disabled" : "") + '>+</button>',
                            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                            '</div>',
                            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                            '<strong>' + formatCurrency(item.price * item.quantity) + '</strong>',
                            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                            '<button type="button" class="cart-remove" data-cart-action="remove" data-menu-id="' + item.id + '">x</button>',
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        '</article>',
                    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                    ].join("");
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                }).join("");
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }

            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            persistState();
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            filterProducts();
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Menambah produk sambil membatasi kuantitas agar tidak melebihi stok yang tersedia.
        function addProduct(card) {
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const id = Number(card.dataset.menuId);
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const stock = Number(card.dataset.stock || 0);
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (!id || stock <= 0) return;

            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const existing = cart.get(id);
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (existing && existing.quantity >= stock) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                showMessage(messageBox, "Stok " + existing.name + " tidak cukup.", "error");
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                return;
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }

            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            cart.set(id, {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                id,
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                name: card.dataset.name || "Menu",
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                price: Number(card.dataset.price || 0),
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                stock,
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                quantity: existing ? existing.quantity + 1 : 1,
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            clearMessage(messageBox);
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            renderCart();
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
        root.querySelectorAll("[data-add-product]").forEach(function (button) {
            // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
            button.addEventListener("click", function () {
                // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
                const card = button.closest("[data-product-card]");
                // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                if (card) addProduct(card);
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });

        // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
        root.querySelectorAll("[data-category-filter]").forEach(function (button) {
            // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
            button.addEventListener("click", function () {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                selectedCategory = normalizeFilterValue(button.dataset.categoryFilter || "all") || "all";
                // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
                root.querySelectorAll("[data-category-filter]").forEach(function (item) {
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    item.classList.toggle("is-active", item === button);
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                });
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                filterProducts();
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });

        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (menuSearchInput) {
            // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
            menuSearchInput.addEventListener("input", filterProducts);
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (cartItems) {
            // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
            cartItems.addEventListener("click", function (event) {
                // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
                const button = event.target.closest("[data-cart-action]");
                // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                if (!button) return;

                // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
                const id = Number(button.dataset.menuId);
                // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
                const item = cart.get(id);
                // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                if (!item) return;

                // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
                const action = button.dataset.cartAction;
                // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                if (action === "plus" && item.quantity < item.stock) {
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    item.quantity += 1;
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                } else if (action === "minus") {
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    item.quantity -= 1;
                    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                    if (item.quantity <= 0) cart.delete(id);
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                } else if (action === "remove") {
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    cart.delete(id);
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                }
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                clearMessage(messageBox);
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                renderCart();
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (openPaymentButton) {
            // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
            openPaymentButton.addEventListener("click", function () {
                // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                if (cart.size === 0) return;
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                persistState();
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                window.location.href = paymentUrl;
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        setSidebarOpen(isSidebarOpen);
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        renderCart();
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Mengaktifkan ringkasan pesanan, pembayaran tunai, QRIS, dan pengiriman checkout ke server.
    function initPaymentPage(root) {
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const checkoutUrl = root.dataset.checkoutUrl;
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const qrisUrl = root.dataset.qrisUrl;
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const posUrl = root.dataset.posUrl || "/pos";
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const state = readState();
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const items = normalizeItems(state.items);
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        let isSubmitting = false;
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        let selectedMethod = state.paymentMethod === "QRIS" ? "QRIS" : "Cash";
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        let cashValue = state.cashValue ? String(state.cashValue) : "";
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        let qrisRequestId = 0;
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        let qrisState = {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            orderCode: "",
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            total: 0,
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            timestamp: "",
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            loading: false,
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            error: false,
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        };

        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const cartItems = root.querySelector("[data-payment-cart-items]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const cartEmpty = root.querySelector("[data-payment-cart-empty]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const cartCountLabel = root.querySelector("[data-payment-count]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const customerNameInput = root.querySelector("[data-customer-name]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const discountInput = root.querySelector("[data-discount-amount]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const messageBox = root.querySelector("[data-payment-message]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const methodButtons = root.querySelectorAll("[data-payment-method]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const paymentModes = root.querySelectorAll("[data-payment-mode]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const completeCashButton = root.querySelector("[data-complete-cash]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const checkQrisButton = root.querySelector("[data-check-qris]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const cashReceived = root.querySelector("[data-cash-received]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const cashChange = root.querySelector("[data-cash-change]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const cashTotal = root.querySelector("[data-cash-total]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const qrisImage = root.querySelector("[data-qris-image]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const qrisPlaceholder = root.querySelector("[data-qris-placeholder]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const qrisTotal = root.querySelector("[data-qris-total]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const qrisOrder = root.querySelector("[data-qris-order]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const qrisStatus = root.querySelector("[data-qris-status]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const summarySubtotalLabels = root.querySelectorAll("[data-summary-subtotal]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const summaryDiscountLabels = root.querySelectorAll("[data-summary-discount]");
        // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
        const summaryTotalLabels = root.querySelectorAll("[data-summary-total]");

        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (customerNameInput) customerNameInput.value = state.customerName || "";
        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (discountInput) discountInput.value = Number(state.discountAmount || 0);

        // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
        function getCashAmount() {
            // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
            return Math.max(0, Number(cashValue || 0) || 0);
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
        function getTotals() {
            // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
            return calculateTotals(items, parseAmount(discountInput));
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
        function savePaymentState() {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            writeState({
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                items,
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                customerName: customerNameInput ? customerNameInput.value : "",
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                discountAmount: parseAmount(discountInput),
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                paymentMethod: selectedMethod,
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                cashValue,
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
        function resetQrisState(message) {
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            qrisRequestId += 1;
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            qrisState = { orderCode: "", total: 0, timestamp: "", loading: false, error: false };
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (qrisImage) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                qrisImage.hidden = true;
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                qrisImage.removeAttribute("src");
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (qrisPlaceholder) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                qrisPlaceholder.hidden = false;
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                qrisPlaceholder.textContent = "QRIS";
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (qrisOrder) qrisOrder.textContent = message || "Invoice akan dibuat setelah keranjang siap.";
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (qrisStatus) qrisStatus.textContent = message || "Menunggu QR dibuat.";
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Fungsi ini mengelompokkan langkah yang dapat dipanggil kembali saat interaksi berlangsung.
        function updatePaymentMethod() {
            // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
            methodButtons.forEach(function (button) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                button.classList.toggle("is-active", button.dataset.paymentMethod === selectedMethod);
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
            // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
            paymentModes.forEach(function (mode) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                mode.classList.toggle("is-active", mode.dataset.paymentMode === selectedMethod);
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Meminta QR baru hanya ketika metode QRIS dipilih dan total pembayaran berubah.
        function ensureQrisCode(total) {
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (selectedMethod !== "QRIS") return;
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (items.length === 0 || total <= 0) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                resetQrisState("Tambahkan menu untuk membuat QRIS.");
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                return;
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (qrisState.orderCode && qrisState.total === total) return;
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (qrisState.loading && qrisState.total === total) return;
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (qrisState.error && qrisState.total === total) return;

            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const requestId = qrisRequestId + 1;
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            qrisRequestId = requestId;
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            qrisState = { orderCode: "", total, timestamp: "", loading: true, error: false };
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (qrisImage) qrisImage.hidden = true;
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (qrisPlaceholder) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                qrisPlaceholder.hidden = false;
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                qrisPlaceholder.textContent = "Loading";
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (qrisOrder) qrisOrder.textContent = "Membuat QRIS...";
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (qrisStatus) qrisStatus.textContent = "Generating QR Code...";
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (checkQrisButton) checkQrisButton.disabled = true;

            // Request POST meminta server membuat kode pesanan dan URL gambar QRIS.
            fetch(qrisUrl, {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                method: "POST",
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                headers: { "Content-Type": "application/json" },
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                body: JSON.stringify({ total_amount: total }),
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            })
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                .then(function (response) {
                    // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
                    return response.json().catch(function () {
                        // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
                        return {};
                    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                    }).then(function (body) {
                        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                        if (!response.ok || !body.success) {
                            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                            throw new Error(body.message || "Gagal membuat QRIS.");
                        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                        }
                        // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
                        return body;
                    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                    });
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                })
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                .then(function (body) {
                    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                    if (requestId !== qrisRequestId) return;
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    qrisState = {
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        orderCode: body.order_code,
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        total,
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        timestamp: body.timestamp,
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        loading: false,
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        error: false,
                    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                    };
                    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                    if (qrisImage) {
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        qrisImage.src = body.qr_url;
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        qrisImage.hidden = false;
                    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                    }
                    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                    if (qrisPlaceholder) qrisPlaceholder.hidden = true;
                    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                    if (qrisOrder) qrisOrder.textContent = body.order_code + " | " + body.timestamp;
                    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                    if (qrisStatus) qrisStatus.textContent = "Menunggu pembayaran QRIS.";
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    renderPayment();
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                })
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                .catch(function (error) {
                    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                    if (requestId !== qrisRequestId) return;
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    qrisState = { orderCode: "", total: 0, timestamp: "", loading: false, error: true };
                    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                    if (qrisImage) {
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        qrisImage.hidden = true;
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        qrisImage.removeAttribute("src");
                    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                    }
                    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                    if (qrisPlaceholder) {
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        qrisPlaceholder.hidden = false;
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        qrisPlaceholder.textContent = "QRIS";
                    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                    }
                    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                    if (qrisOrder) qrisOrder.textContent = error.message;
                    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                    if (qrisStatus) qrisStatus.textContent = error.message;
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    showMessage(messageBox, error.message, "error");
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    renderPayment();
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Memperbarui tampilan nominal, kembalian, tombol aktif, dan ringkasan pembayaran.
        function renderPayment() {
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const totals = getTotals();
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const received = getCashAmount();
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const change = Math.max(received - totals.total, 0);
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const hasItems = items.length > 0;

            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (cartEmpty) cartEmpty.hidden = hasItems;
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (cartCountLabel) cartCountLabel.textContent = totals.itemCount + (totals.itemCount === 1 ? " Item" : " Items");
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            setTextAll(summarySubtotalLabels, formatCurrency(totals.subtotal));
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            setTextAll(summaryDiscountLabels, formatCurrency(totals.discount));
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            setTextAll(summaryTotalLabels, formatCurrency(totals.total));
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (cashReceived) cashReceived.textContent = formatCurrency(received);
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (cashChange) cashChange.textContent = formatCurrency(change);
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (cashTotal) cashTotal.textContent = formatCurrency(totals.total);
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (qrisTotal) qrisTotal.textContent = formatCurrency(totals.total);

            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (cartItems) {
                // Map mengubah setiap elemen menjadi bentuk data yang diperlukan berikutnya.
                cartItems.innerHTML = items.map(function (item) {
                    // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
                    return [
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        '<article class="payment-cart-item">',
                            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                            '<div>',
                                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                                '<strong>' + escapeHtml(item.name) + '</strong>',
                                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                                '<span>' + item.quantity + ' x ' + formatCurrency(item.price) + '</span>',
                            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                            '</div>',
                            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                            '<b>' + formatCurrency(item.price * item.quantity) + '</b>',
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        '</article>',
                    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                    ].join("");
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                }).join("");
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }

            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (completeCashButton) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                completeCashButton.disabled = isSubmitting || !hasItems || totals.total <= 0 || received < totals.total;
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (checkQrisButton) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                checkQrisButton.disabled = (
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    isSubmitting ||
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    !hasItems ||
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    totals.total <= 0 ||
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    qrisState.loading ||
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    !qrisState.orderCode
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                );
                // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                if (!isSubmitting) {
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    checkQrisButton.textContent = "Check Payment Status";
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                }
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            }

            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            updatePaymentMethod();
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            savePaymentState();
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            ensureQrisCode(totals.total);
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Menyusun payload minimal yang akan divalidasi ulang dan disimpan oleh endpoint checkout Flask.
        function buildCheckoutPayload(method, options) {
            // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
            const totals = getTotals();
            // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
            return {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                customer_name: customerNameInput ? customerNameInput.value : "",
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                payment_method: method,
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                order_code: options && options.orderCode ? options.orderCode : "",
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                received_amount: options && options.receivedAmount !== undefined ? options.receivedAmount : totals.total,
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                change_amount: options && options.changeAmount !== undefined ? options.changeAmount : 0,
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                discount_amount: totals.discount,
                // Map mengubah setiap elemen menjadi bentuk data yang diperlukan berikutnya.
                items: items.map(function (item) {
                    // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
                    return { menu_id: item.id, quantity: item.quantity };
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                }),
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            };
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Mengirim transaksi sekali saja dan berpindah ke halaman sukses setelah server menyimpannya.
        function submitPayment(method, options) {
            // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
            if (items.length === 0 || isSubmitting) return;

            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            isSubmitting = true;
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            renderPayment();
            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
            clearMessage(messageBox);

            // Fetch mengirim request ke endpoint Flask dan menunggu respons dari server.
            fetch(checkoutUrl, {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                method: "POST",
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                headers: { "Content-Type": "application/json" },
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                body: JSON.stringify(buildCheckoutPayload(method, options || {})),
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            })
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                .then(function (response) {
                    // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
                    return response.json().catch(function () {
                        // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
                        return {};
                    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                    }).then(function (body) {
                        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                        if (!response.ok || !body.success) {
                            // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                            throw new Error(body.message || "Transaksi gagal disimpan.");
                        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                        }
                        // Mengembalikan hasil ini kepada pemanggil fungsi JavaScript.
                        return body;
                    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                    });
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                })
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                .then(function (body) {
                    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
                    const transaction = body.transaction || {};
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    clearState();
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    window.location.href = transaction.success_url || "/pos";
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                })
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                .catch(function (error) {
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    showMessage(messageBox, error.message, "error");
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    isSubmitting = false;
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    renderPayment();
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
        root.querySelectorAll("[data-payment-back]").forEach(function (link) {
            // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
            link.addEventListener("click", function (event) {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                event.preventDefault();
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                savePaymentState();
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                window.location.href = posUrl;
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });

        // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
        methodButtons.forEach(function (button) {
            // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
            button.addEventListener("click", function () {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                selectedMethod = button.dataset.paymentMethod === "QRIS" ? "QRIS" : "Cash";
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                clearMessage(messageBox);
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                renderPayment();
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });

        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (customerNameInput) {
            // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
            customerNameInput.addEventListener("input", savePaymentState);
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (discountInput) {
            // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
            discountInput.addEventListener("input", function () {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                resetQrisState("Total berubah. QRIS akan dibuat ulang.");
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                clearMessage(messageBox);
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                renderPayment();
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
        root.querySelectorAll("[data-quick-cash]").forEach(function (button) {
            // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
            button.addEventListener("click", function () {
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                cashValue = button.dataset.quickCash || "";
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                clearMessage(messageBox);
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                renderPayment();
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });

        // Perulangan ini menerapkan proses yang sama pada setiap elemen dalam koleksi.
        root.querySelectorAll("[data-cash-key]").forEach(function (button) {
            // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
            button.addEventListener("click", function () {
                // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
                const key = button.dataset.cashKey;
                // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                if (key === "clear") {
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    cashValue = "";
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                } else if (key === "back") {
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    cashValue = cashValue.slice(0, -1);
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                } else if (cashValue.length < 10) {
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    cashValue = (cashValue + key).replace(/^0+(?=\d)/, "");
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                }
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                clearMessage(messageBox);
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                renderPayment();
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        });

        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (completeCashButton) {
            // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
            completeCashButton.addEventListener("click", function () {
                // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
                const totals = getTotals();
                // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
                const received = getCashAmount();
                // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                if (received < totals.total) {
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    showMessage(messageBox, "Nominal diterima kurang dari total pembayaran.", "error");
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    return;
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                }
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                submitPayment("Cash", {
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    receivedAmount: received,
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    changeAmount: Math.max(received - totals.total, 0),
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                });
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
        if (checkQrisButton) {
            // Event listener ini menjalankan respons ketika pengguna atau browser memicu kejadian terkait.
            checkQrisButton.addEventListener("click", function () {
                // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
                const totals = getTotals();
                // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                if (!qrisState.orderCode) {
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    showMessage(messageBox, "QRIS belum siap. Tunggu QR Code selesai dibuat.", "error");
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    return;
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                }

                // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                if (qrisStatus) qrisStatus.textContent = "Checking payment status...";
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                checkQrisButton.disabled = true;
                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                checkQrisButton.textContent = "Checking...";

                // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                window.setTimeout(function () {
                    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
                    if (qrisStatus) qrisStatus.textContent = "Payment Success";
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    checkQrisButton.textContent = "Payment Success";
                    // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                    submitPayment("QRIS", {
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        orderCode: qrisState.orderCode,
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        receivedAmount: totals.total,
                        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
                        changeAmount: 0,
                    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                    });
                // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
                }, 2300);
            // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
            });
        // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
        }

        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        resetQrisState();
        // Menjalankan langkah ini untuk memperbarui data atau keadaan antarmuka.
        renderPayment();
    // Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
    }

    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const posPage = document.querySelector("[data-pos-cart]");
    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
    if (posPage) initPosPage(posPage);

    // Menyimpan referensi atau nilai yang digunakan oleh proses JavaScript berikutnya.
    const paymentPage = document.querySelector("[data-payment-page]");
    // Kondisi ini mencegah proses yang tidak sesuai dengan keadaan data atau elemen saat ini.
    if (paymentPage) initPaymentPage(paymentPage);
// Menutup blok, pemanggilan, atau susunan data yang dimulai sebelumnya.
});
