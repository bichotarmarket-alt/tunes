"""
Gerenciador de conexão ngrok com salvamento automático no Google Sheets
"""
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from loguru import logger
import os


class NgrokManager:
    """Gerencia conexão ngrok e salva URL no Google Sheets"""

    def __init__(self, sheet_id: str = None):
        self.sheet_id = sheet_id or os.getenv('GOOGLE_SHEET_ID')
        self.ngrok_url = None
        self.gc = None

    def _init_google_sheets(self):
        """Inicializa conexão com Google Sheets"""
        try:
            scope = ['https://spreadsheets.google.com/feeds']
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                'google_credentials.json', scope
            )
            self.gc = gspread.authorize(credentials)
            logger.info("✓ Conectado ao Google Sheets")
            return True
        except Exception as e:
            logger.error(f"✗ Erro ao conectar ao Google Sheets: {e}")
            return False

    def get_ngrok_url(self) -> str | None:
        """
        Captura URL do ngrok via API local

        Returns:
            URL do ngrok ou None se não conseguir capturar
        """
        try:
            response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=5)
            response.raise_for_status()
            data = response.json()

            if 'tunnels' in data and len(data['tunnels']) > 0:
                self.ngrok_url = data['tunnels'][0]['public_url']
                logger.info(f"✓ URL do ngrok capturado: {self.ngrok_url}")
                return self.ngrok_url
            else:
                logger.warning("✗ Nenhum túnel ngrok encontrado")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Erro ao capturar URL do ngrok: {e}")
            return None
        except Exception as e:
            logger.error(f"✗ Erro inesperado ao capturar URL: {e}")
            return None

    def save_url_to_google_sheets(self, url: str) -> bool:
        """
        Salva URL do ngrok no Google Sheets

        Args:
            url: URL do ngrok para salvar

        Returns:
            True se salvou com sucesso, False caso contrário
        """
        if not self.gc and not self._init_google_sheets():
            return False

        try:
            sheet = self.gc.open_by_key(self.sheet_id)
            worksheet = sheet.sheet1

            # Atualizar célula A1 com o URL usando update_cell
            worksheet.update_cell(1, 1, url)
            logger.info(f"✓ URL salvo no Google Sheets: {url}")
            return True

        except Exception as e:
            logger.error(f"✗ Erro ao salvar no Google Sheets: {e}")
            return False

    def get_url_from_google_sheets(self) -> str | None:
        """
        Lê URL do ngrok do Google Sheets

        Returns:
            URL do ngrok ou None se não conseguir ler
        """
        if not self.gc and not self._init_google_sheets():
            return None

        try:
            sheet = self.gc.open_by_key(self.sheet_id)
            worksheet = sheet.sheet1

            # Ler célula A1
            url = worksheet.acell('A1').value
            logger.info(f"✓ URL lido do Google Sheets: {url}")
            return url

        except Exception as e:
            logger.error(f"✗ Erro ao ler do Google Sheets: {e}")
            return None

    def update_and_save(self) -> bool:
        """
        Captura URL do ngrok e salva no Google Sheets

        Returns:
            True se atualizou com sucesso, False caso contrário
        """
        url = self.get_ngrok_url()
        if url:
            return self.save_url_to_google_sheets(url)
        return False
