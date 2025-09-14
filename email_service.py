import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_otp_email(to_email, otp):
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_username = os.getenv('SMTP_USERNAME')
    smtp_password = os.getenv('SMTP_PASSWORD')

    # Validate configuration
    if not all([smtp_username, smtp_password]):
        logger.error("SMTP credentials are not properly configured")
        return False

    # Create message
    msg = MIMEMultipart()
    msg['From'] = f"Study Smart Timer <{smtp_username}>"
    msg['To'] = to_email
    msg['Subject'] = 'Your Study Smart Timer OTP'

    body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #f8f9fa; padding: 20px; text-align: center;">
                <h2 style="color: #3730A3;">Study Smart Timer - One-Time Password</h2>
                <div style="background-color: white; border-radius: 8px; padding: 20px; margin: 20px 0;">
                    <p>Your OTP for authentication is:</p>
                    <h1 style="color: #4F46E5; letter-spacing: 5px; font-size: 32px;">{otp}</h1>
                    <p style="color: #6B7280; font-size: 14px;">This OTP will expire in 10 minutes.</p>
                </div>
                <p style="color: #9CA3AF; font-size: 12px;">If you didn't request this OTP, please ignore this email.</p>
            </div>
        </body>
    </html>
    """
    msg.attach(MIMEText(body, 'html'))

    try:
        logger.info(f"Attempting to connect to SMTP server {smtp_server}:{smtp_port}")
        server = smtplib.SMTP(smtp_server, smtp_port)
        
        logger.info("Starting TLS connection")
        server.starttls()
        
        logger.info("Attempting login with provided credentials")
        server.login(smtp_username, smtp_password)
        
        logger.info(f"Sending email to {to_email}")
        text = msg.as_string()
        server.sendmail(smtp_username, to_email, text)
        
        logger.info("Email sent successfully")
        server.quit()
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication failed: {str(e)}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error occurred: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while sending email: {str(e)}")
        return False
