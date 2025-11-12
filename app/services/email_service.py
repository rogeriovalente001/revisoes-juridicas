"""
Serviço de Email para Revisões Jurídicas
"""

import os
import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, url_for

logger = logging.getLogger(__name__)


class EmailService:
    """Serviço para envio de emails"""
    
    def __init__(self):
        self.email_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'emails')
        os.makedirs(self.email_dir, exist_ok=True)
    
    def send_approval_request_email(self, approver_email: str, approver_name: str, 
                                   review_data: dict, approval_url: str) -> bool:
        """Envia email de solicitação de aprovação"""
        subject = f"Revisão Jurídica Pendente de Aprovação - {review_data.get('title', 'Documento')}"
        html_content = self._get_approval_request_template(
            approver_name, review_data, approval_url
        )
        
        return self._send_email(approver_email, subject, html_content)
    
    def send_approval_confirmation_email(self, reviewer_email: str, reviewer_name: str,
                                        approver_name: str, review_data: dict, 
                                        status: str, comments: str) -> bool:
        """Envia email de confirmação de aprovação/rejeição"""
        subject = f"Revisão Jurídica {'Aprovada' if status == 'approved' else 'Rejeitada'} - {review_data.get('title', 'Documento')}"
        html_content = self._get_approval_confirmation_template(
            reviewer_name, approver_name, review_data, status, comments
        )
        
        return self._send_email(reviewer_email, subject, html_content)
    
    def _get_approval_request_template(self, approver_name: str, review_data: dict, approval_url: str) -> str:
        """Template HTML para email de solicitação de aprovação"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Solicitação de Aprovação - Revisão Jurídica</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f0f0f0;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #f0f0f0; padding: 20px;">
                <tr>
                    <td align="center">
                        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width: 600px; background-color: #ffffff; border-radius: 15px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <tr>
                                <td style="background: linear-gradient(135deg, #8B5CF6 0%, #7C3AED 100%); color: #ffffff; padding: 30px; text-align: center;">
                                    <h1 style="margin: 0; font-size: 28px; font-weight: bold;">Revisão Jurídica Pendente</h1>
                                    <p style="margin: 10px 0 0 0; font-size: 16px;">Sistema de Revisões Jurídicas</p>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 40px;">
                                    <h2 style="margin: 0 0 15px 0; font-size: 24px; color: #333;">Olá, {approver_name}!</h2>
                                    <p style="margin: 0 0 25px 0; font-size: 16px; color: #333;">
                                        Você foi solicitado para aprovar uma revisão jurídica de documento estratégico.
                                    </p>
                                    
                                    <div style="background-color: #f8f9fa; border-left: 4px solid #8B5CF6; padding: 20px; margin: 20px 0; border-radius: 4px;">
                                        <h3 style="margin: 0 0 10px 0; font-size: 18px; color: #333;">Informações do Documento</h3>
                                        <p style="margin: 5px 0;"><strong>Título:</strong> {review_data.get('title', 'N/A')}</p>
                                        <p style="margin: 5px 0;"><strong>Descrição:</strong> {str(review_data.get('description', 'N/A'))[:200]}{'...' if review_data.get('description') and len(str(review_data.get('description', ''))) > 200 else ''}</p>
                                        <p style="margin: 5px 0;"><strong>Versão:</strong> v{review_data.get('version', 'N/A')}</p>
                                        <p style="margin: 5px 0;"><strong>Revisor:</strong> {review_data.get('reviewer_name', 'N/A')}</p>
                                        <p style="margin: 5px 0;"><strong>Data da Revisão:</strong> {review_data.get('review_date').strftime('%d/%m/%Y %H:%M:%S') if review_data.get('review_date') and hasattr(review_data.get('review_date'), 'strftime') else str(review_data.get('review_date', 'N/A'))}</p>
                                    </div>
                                    
                                    <div style="text-align: center; padding: 25px 0;">
                                        <a href="{approval_url}" style="display: inline-block; background: linear-gradient(135deg, #8B5CF6 0%, #7C3AED 100%); color: #ffffff; padding: 15px 35px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px; box-shadow: 0 4px 15px rgba(139, 92, 246, 0.3);">
                                            Revisar e Aprovar
                                        </a>
                                    </div>
                                    
                                    <p style="margin: 20px 0 0 0; font-size: 14px; color: #666;">
                                        <strong>Importante:</strong> O comentário é obrigatório ao aprovar ou rejeitar a revisão.
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
    
    def _get_approval_confirmation_template(self, reviewer_name: str, approver_name: str,
                                           review_data: dict, status: str, comments: str) -> str:
        """Template HTML para email de confirmação de aprovação"""
        status_text = "Aprovada" if status == "approved" else "Rejeitada"
        status_color = "#10B981" if status == "approved" else "#EF4444"
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Revisão {status_text} - Revisão Jurídica</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f0f0f0;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #f0f0f0; padding: 20px;">
                <tr>
                    <td align="center">
                        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width: 600px; background-color: #ffffff; border-radius: 15px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <tr>
                                <td style="background: linear-gradient(135deg, {status_color} 0%, {status_color}dd 100%); color: #ffffff; padding: 30px; text-align: center;">
                                    <h1 style="margin: 0; font-size: 28px; font-weight: bold;">Revisão {status_text}</h1>
                                    <p style="margin: 10px 0 0 0; font-size: 16px;">Sistema de Revisões Jurídicas</p>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 40px;">
                                    <h2 style="margin: 0 0 15px 0; font-size: 24px; color: #333;">Olá, {reviewer_name}!</h2>
                                    <p style="margin: 0 0 25px 0; font-size: 16px; color: #333;">
                                        Sua revisão jurídica foi <strong>{status_text.lower()}</strong> por <strong>{approver_name}</strong>.
                                    </p>
                                    
                                    <div style="background-color: #f8f9fa; border-left: 4px solid {status_color}; padding: 20px; margin: 20px 0; border-radius: 4px;">
                                        <h3 style="margin: 0 0 10px 0; font-size: 18px; color: #333;">Informações da Revisão</h3>
                                        <p style="margin: 5px 0;"><strong>Título:</strong> {review_data.get('title', 'N/A')}</p>
                                        <p style="margin: 5px 0;"><strong>Versão:</strong> {review_data.get('version', 'N/A')}</p>
                                        <p style="margin: 5px 0;"><strong>Aprovador:</strong> {approver_name}</p>
                                        <p style="margin: 5px 0;"><strong>Data/Hora:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
                                    </div>
                                    
                                    <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px; padding: 15px; margin: 20px 0;">
                                        <h4 style="margin: 0 0 10px 0; font-size: 16px; color: #856404;">Comentário do Aprovador:</h4>
                                        <p style="margin: 0; color: #856404; white-space: pre-wrap;">{comments}</p>
                                    </div>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
    
    def _send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """Envia email via SMTP ou salva em arquivo"""
        try:
            # Tentar enviar via SMTP
            if self._try_smtp_send(to_email, subject, html_content):
                return True
            
            # Fallback: salvar em arquivo
            return self._save_email_to_file(to_email, subject, html_content)
        except Exception as e:
            logger.error(f"Erro ao enviar email: {str(e)}")
            return False
    
    def _try_smtp_send(self, to_email: str, subject: str, html_content: str) -> bool:
        """Tenta enviar email via SMTP"""
        try:
            mail_server = os.getenv('MAIL_SERVER')
            mail_port = int(os.getenv('MAIL_PORT', 587))
            mail_username = os.getenv('MAIL_USERNAME')
            mail_password = os.getenv('MAIL_PASSWORD')
            mail_use_tls = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
            
            if not mail_server or not mail_username:
                return False
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = mail_username
            msg['To'] = to_email
            
            msg.attach(MIMEText(html_content, 'html'))
            
            server = smtplib.SMTP(mail_server, mail_port)
            if mail_use_tls:
                server.starttls()
            server.login(mail_username, mail_password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email enviado via SMTP para: {to_email}")
            return True
        except Exception as e:
            logger.warning(f"Falha ao enviar email via SMTP: {str(e)}")
            return False
    
    def _save_email_to_file(self, to_email: str, subject: str, html_content: str) -> bool:
        """Salva email em arquivo para desenvolvimento"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"email_{timestamp}_{to_email.replace('@', '_at_')}.html"
            filepath = os.path.join(self.email_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"<h2>Para: {to_email}</h2>")
                f.write(f"<h3>Assunto: {subject}</h3>")
                f.write("<hr>")
                f.write(html_content)
            
            logger.info(f"Email salvo em arquivo: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar email em arquivo: {str(e)}")
            return False


# Instância global do serviço
email_service = EmailService()

