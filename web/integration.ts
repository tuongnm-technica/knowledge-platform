import { authFetch } from './client';
import { AuthModule } from './auth';
import { showToast } from './ui';

export class IntegrationModule {
    private isInitialized = false;

    public async init() {
        if (this.isInitialized) return;

        console.log('Integrations Module rendering...');
        const user = await AuthModule.getCurrentUser();
        if (!user || (!user.is_admin && user.role !== 'system_admin')) {
            showToast('Bạn không có quyền truy cập trang này.', 'error');
            return;
        }

        this.bindEvents();
        await this.loadSmtpSettings();
        this.isInitialized = true;
    }

    private bindEvents() {
        const authCheckbox = document.getElementById('smtpAuthEnabled') as HTMLInputElement;
        if (authCheckbox) {
            authCheckbox.addEventListener('change', () => {
                const isChecked = authCheckbox.checked;
                const usr = document.getElementById('smtpUsername') as HTMLInputElement;
                const pwd = document.getElementById('smtpPassword') as HTMLInputElement;
                if (usr) usr.disabled = !isChecked;
                if (pwd) pwd.disabled = !isChecked;
                if (!isChecked) {
                    if (usr) usr.value = '';
                    if (pwd) pwd.value = '';
                }
            });
        }

        const saveBtn = document.getElementById('saveSmtpBtn');
        if (saveBtn) {
            saveBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.saveSmtpSettings();
            });
        }
        
        const testBtn = document.getElementById('sendTestMailBtn');
        if (testBtn) {
            testBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.sendTestMail();
            });
        }
    }

    private async loadSmtpSettings() {
        try {
            const res = await authFetch('/api/settings/smtp');
            if (res.ok) {
                const data = await res.json();
                if (data && Object.keys(data).length > 0) {
                (document.getElementById('smtpHost') as HTMLInputElement).value = data.smtp_host || '';
                (document.getElementById('smtpPort') as HTMLInputElement).value = data.smtp_port || '';
                (document.getElementById('smtpSecurity') as HTMLSelectElement).value = data.security_mode || 'STARTTLS';
                
                const authEnabled = data.authentication_enabled || false;
                const authCheckbox = document.getElementById('smtpAuthEnabled') as HTMLInputElement;
                authCheckbox.checked = authEnabled;
                
                const usr = document.getElementById('smtpUsername') as HTMLInputElement;
                const pwd = document.getElementById('smtpPassword') as HTMLInputElement;
                
                if (authEnabled) {
                    usr.disabled = false;
                    pwd.disabled = false;
                    usr.value = data.smtp_username || '';
                    // Prevent masking from triggering change validation issues directly on UI
                    pwd.value = data.smtp_password || '';
                } else {
                    usr.disabled = true;
                    pwd.disabled = true;
                }
                
                (document.getElementById('smtpSenderEmail') as HTMLInputElement).value = data.sender_email_address || '';
                (document.getElementById('smtpSenderName') as HTMLInputElement).value = data.sender_display_name || '';
                
                document.getElementById('smtpStatusText')!.innerHTML = '<span style="color:var(--success)">Saved</span>';
            } else {
                document.getElementById('smtpStatusText')!.innerHTML = '<span style="color:var(--text-dim)">Never Tested / No Config</span>';
            }
            }
        } catch (error) {
            console.error('Failed to load SMTP settings:', error);
            showToast('Không thể tải cấu hình SMTP.', 'error');
        }
    }

    private async saveSmtpSettings() {
        const payload = {
            smtp_host: (document.getElementById('smtpHost') as HTMLInputElement).value,
            smtp_port: parseInt((document.getElementById('smtpPort') as HTMLInputElement).value) || 0,
            security_mode: (document.getElementById('smtpSecurity') as HTMLSelectElement).value,
            authentication_enabled: (document.getElementById('smtpAuthEnabled') as HTMLInputElement).checked,
            smtp_username: (document.getElementById('smtpUsername') as HTMLInputElement).value || null,
            smtp_password: (document.getElementById('smtpPassword') as HTMLInputElement).value || null,
            sender_email_address: (document.getElementById('smtpSenderEmail') as HTMLInputElement).value,
            sender_display_name: (document.getElementById('smtpSenderName') as HTMLInputElement).value,
        };

        if (!payload.smtp_host || !payload.smtp_port || !payload.sender_email_address || !payload.sender_display_name) {
            showToast('Vui lòng điền đầy đủ các trường bắt buộc (*)', 'warning');
            return;
        }

        try {
            const btn = document.getElementById('saveSmtpBtn') as HTMLButtonElement;
            btn.disabled = true;
            btn.textContent = 'Saving...';
            
            const req = await authFetch('/api/settings/smtp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!req.ok) throw new Error(await req.text() || 'Save failed');
            
            showToast('Đã lưu cấu hình SMTP thành công!', 'success');
            document.getElementById('smtpStatusText')!.innerHTML = '<span style="color:var(--success)">Configuration Saved</span>';
            await this.loadSmtpSettings(); // Reload to capture masked password
        } catch (error: any) {
            console.error('Save failed:', error);
            showToast(error.message || 'Lưu cấu hình thất bại.', 'error');
        } finally {
            const btn = document.getElementById('saveSmtpBtn') as HTMLButtonElement;
            btn.disabled = false;
            btn.textContent = 'Save SMTP Settings';
        }
    }
    
    private async sendTestMail() {
        const payload = {
            recipient: (document.getElementById('testEmailRecipient') as HTMLInputElement).value,
            body: (document.getElementById('testEmailBody') as HTMLTextAreaElement).value
        };
        
        if (!payload.recipient) {
            showToast('Vui lòng nhập email người nhận.', 'warning');
            return;
        }

        try {
            const btn = document.getElementById('sendTestMailBtn') as HTMLButtonElement;
            btn.disabled = true;
            btn.textContent = 'Sending test email...';
            
            const reqRes = await authFetch('/api/settings/smtp/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const res = reqRes.ok ? await reqRes.json() : { message: 'Lỗi máy chủ' };
            showToast(res.message || 'Email thử nghiệm đã được gửi.', 'success');
        } catch (error: any) {
            console.error('Test mail failed:', error);
            showToast(error.message || 'Gửi test mail thất bại.', 'error');
        } finally {
            const btn = document.getElementById('sendTestMailBtn') as HTMLButtonElement;
            btn.disabled = false;
            btn.textContent = 'Send Test Mail';
        }
    }
}

export const integrationModule = new IntegrationModule();
