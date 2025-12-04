import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.header import Header
from .logger import Logger

class Mailer:
    def __init__(self, smtp_server, smtp_port, sender_email, sender_password):
        self.smtp_server = smtp_server
        self.smtp_port = int(smtp_port)
        self.sender_email = sender_email
        self.sender_password = sender_password

    def send_link_notification(self, to_emails_str, url, qr_code_path=None):
        """
        发送邮件通知，支持多个收件人和二维码图片附件
        :param to_emails_str: 收件人邮箱字符串，多个邮箱用逗号或分号分隔
        :param url: 远程访问链接
        :param qr_code_path: 二维码图片路径 (可选)
        """
        # 处理多个收件人
        to_emails = [email.strip() for email in to_emails_str.replace(';', ',').split(',') if email.strip()]
        if not to_emails:
            Logger.error("没有有效的收件人邮箱")
            return False

        subject = "【A to W Player】远程访问地址更新"
        
        # 创建混合类型的邮件对象
        message = MIMEMultipart('related')
        message['From'] = Header(f"A to W Server <{self.sender_email}>", 'utf-8')
        message['To'] = Header(','.join(to_emails), 'utf-8')
        message['Subject'] = Header(subject, 'utf-8')
        
        msg_alternative = MIMEMultipart('alternative')
        message.attach(msg_alternative)

        # HTML 内容，包含图片引用
        html_content = f"""
        <html>
          <body>
            <p>您的汽水音乐远程控制地址已更新。</p>
            <p>新的访问地址为：<br>
            <a href="{url}">{url}</a></p>
            <p>您可以直接点击链接，或者扫描下方二维码访问：</p>
            <p><img src="cid:qrcode_image"></p>
            <hr>
            <p style="color:gray;font-size:12px;">如果这不是您的操作，请检查服务运行状态。</p>
          </body>
        </html>
        """
        msg_alternative.attach(MIMEText(html_content, 'html', 'utf-8'))

        # 如果提供了二维码图片路径，则添加附件
        if qr_code_path and os.path.exists(qr_code_path):
            try:
                with open(qr_code_path, 'rb') as f:
                    msg_image = MIMEImage(f.read())
                    msg_image.add_header('Content-ID', '<qrcode_image>')
                    msg_image.add_header('Content-Disposition', 'inline', filename='qrcode.png')
                    message.attach(msg_image)
            except Exception as e:
                Logger.error(f"读取二维码图片失败: {e}")

        try:
            Logger.info(f"正在连接邮件服务器 {self.smtp_server}...")
            
            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                # 尝试启用TLS，如果端口不是465
                try:
                    server.starttls()
                except:
                    pass
            
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, to_emails, message.as_string())
            server.quit()
            Logger.info(f"邮件通知已成功发送至 {', '.join(to_emails)}")
            return True
        except Exception as e:
            Logger.error(f"邮件发送失败: {str(e)}")
            return False
