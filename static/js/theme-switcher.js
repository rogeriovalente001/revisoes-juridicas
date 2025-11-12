/**
 * REVISÕES JURÍDICAS - Theme Switcher
 * Sistema de alternância entre temas claro e escuro
 */

class ThemeSwitcher {
    constructor() {
        this.currentTheme = this.getStoredTheme() || 'light';
        this.init();
    }

    init() {
        this.applyTheme(this.currentTheme);
        this.createThemeButton();
        this.bindEvents();
    }

    getStoredTheme() {
        return localStorage.getItem('revisoes-juridicas-theme');
    }

    setStoredTheme(theme) {
        localStorage.setItem('revisoes-juridicas-theme', theme);
    }

    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        this.currentTheme = theme;
        this.setStoredTheme(theme);
        
        // Atualizar ícone do botão se existir
        const themeButton = document.getElementById('theme-switcher-btn');
        if (themeButton) {
            const icon = themeButton.querySelector('i');
            if (icon) {
                icon.className = theme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
            }
        }
    }

    toggleTheme() {
        const newTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        this.applyTheme(newTheme);
    }

    createThemeButton() {
        // Verificar se o botão já existe (foi criado no template)
        const themeButton = document.getElementById('theme-switcher-btn');
        if (!themeButton) {
            console.warn('Botão de tema não encontrado no template');
            return;
        }

        // Atualizar título do botão
        themeButton.title = `Alternar para tema ${this.currentTheme === 'light' ? 'escuro' : 'claro'}`;
        
        // Adicionar hover effect se não existir
        if (!themeButton.hasAttribute('data-hover-added')) {
            themeButton.setAttribute('data-hover-added', 'true');
            themeButton.addEventListener('mouseenter', function() {
                this.style.transform = 'scale(1.1)';
            });

            themeButton.addEventListener('mouseleave', function() {
                this.style.transform = 'scale(1)';
            });
        }
    }

    bindEvents() {
        // Event listener para o botão
        document.addEventListener('click', (e) => {
            if (e.target.closest('#theme-switcher-btn')) {
                e.preventDefault();
                this.toggleTheme();
            }
        });

        // Atalho de teclado (Ctrl + Shift + T)
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.key === 'T') {
                e.preventDefault();
                this.toggleTheme();
            }
        });

        // Detectar mudanças de tema do sistema (se suportado)
        if (window.matchMedia) {
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            mediaQuery.addListener((e) => {
                // Só aplicar se o usuário não tiver preferência salva
                if (!this.getStoredTheme()) {
                    this.applyTheme(e.matches ? 'dark' : 'light');
                }
            });
        }
    }

    // Método público para obter tema atual
    getCurrentTheme() {
        return this.currentTheme;
    }

    // Método público para definir tema programaticamente
    setTheme(theme) {
        if (theme === 'light' || theme === 'dark') {
            this.applyTheme(theme);
        }
    }
}

// Inicializar quando o DOM estiver carregado
document.addEventListener('DOMContentLoaded', function() {
    window.themeSwitcher = new ThemeSwitcher();
});

// Exportar para uso global
window.ThemeSwitcher = ThemeSwitcher;

