import sys
import os, ssl
import configparser
import time
import shutil
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QFileDialog, QMessageBox, QVBoxLayout, QPushButton, QLabel, QProgressBar, QCheckBox, QLineEdit, QTextEdit, QWidget, QDialog, QTextBrowser, QDesktopWidget
from PyQt5.QtCore import QSettings, QThread, pyqtSignal
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
if (not os.environ.get('PYTHONHTTPSVERIFY', '') and
    getattr(ssl, '_create_unverified_context', None)):
    ssl._create_default_https_context = ssl._create_unverified_context


class FileUpdater(QThread):
    start_update = pyqtSignal(int)
    update_progress = pyqtSignal(int, str)
    finished_update = pyqtSignal(list, list, bool)
    checking_file = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, src, dest):
        super(FileUpdater, self).__init__()
        self.src = src
        self.dest = dest
        self.files_failed = []

    def run(self):
        print("Início da atualização...")
        files_to_copy = []
        files_failed = []  # Para manter uma lista dos arquivos que falharam
        files_successfully_copied = []

        try:
            # Lista todos os arquivos na origem
            all_files = [os.path.join(root, file) for root, _, files in os.walk(self.src) for file in files]
            total_files = len(all_files)

            # Verificar todos os arquivos na origem
            for index, src_file in enumerate(all_files, 1):
                dest_dir = self.dest if self.dest.endswith(os.sep) else self.dest + os.sep
                dest_file = src_file.replace(self.src, self.dest)
                print(f"Verificando arquivo {index}/{total_files}: {src_file}")  # Log
                self.checking_file.emit(f"Verificando arquivo {index}/{total_files}: {src_file}")

                # Verificar se o arquivo deve ser copiado (se não existe ou está desatualizado)
                if not os.path.exists(dest_file) or os.path.getmtime(src_file) > os.path.getmtime(dest_file):
                    files_to_copy.append(src_file)

            # Emitir sinal com total de arquivos a copiar
            self.start_update.emit(len(files_to_copy))

            # Copiar arquivos
            for index, src_file in enumerate(files_to_copy, 1):
                dest_file = os.path.normpath(src_file.replace(self.src, self.dest))
                print(f"Transferindo {index}/{len(files_to_copy)}: {src_file}")  # Log

                # Emitir o sinal somente com o nome do arquivo sendo transferido
                self.update_progress.emit(index, f"{index}/{len(files_to_copy)}: {os.path.basename(src_file)}")

                # Garantir que o diretório de destino exista
                os.makedirs(os.path.dirname(dest_file), exist_ok=True)

                try:
                    # Tentativa de copiar o arquivo
                    shutil.copy2(src_file, dest_file)
                    files_successfully_copied.append(src_file)  # Adicionar o arquivo à lista de sucesso
                except PermissionError:
                    # error_msg = f"Erro ao copiar arquivo {src_file}. O arquivo está sendo usado."
                    # self.error_signal.emit(error_msg)  # Esta linha foi comentada
                    files_failed.append(src_file)  # Adicionar o arquivo à lista de falhas
                    continue  # Continuar com o próximo arquivo

                time.sleep(0.01)  # Pausa de 10ms

            # Emitir sinal de conclusão
            self.finished_update.emit(files_successfully_copied, files_failed, True)

        except Exception as e:
            print(f"Erro geral durante a atualização: {e}")
            self.finished_update.emit([], [], False)

        if files_failed:
            print("Alguns arquivos falharam ao copiar:")
            for f in files_failed:
                print(f)


class TransferLogDialog(QDialog):
    def __init__(self, files):
        super().__init__()
        self.setWindowTitle('Arquivos Transferidos')
        layout = QVBoxLayout()
        text_browser = QTextBrowser(self)
        text_browser.append('\n'.join(files))
        layout.addWidget(text_browser)
        self.setLayout(layout)

class App(QMainWindow):

    def __init__(self):
        super().__init__()
        self.title = 'Atualizador de Arquivos'
        self.left = 10
        self.top = 10
        self.width = 640
        self.height = 240
        self.config = configparser.ConfigParser()
        self.initUI()

    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)

        # Widgets
        self.src_label = QLabel("Diretório de Origem:")
        self.src_input = QLineEdit(self)
        self.src_browse_btn = QPushButton('Procurar', self)
        self.src_browse_btn.clicked.connect(self.browse_src)

        self.dest_label = QLabel("Diretório de Destino:")
        self.dest_input = QLineEdit(self)
        self.dest_browse_btn = QPushButton('Procurar', self)
        self.dest_browse_btn.clicked.connect(self.browse_dest)

        self.auto_update_checkbox = QCheckBox("Atualizar automaticamente ao abrir o aplicativo", self)

        self.save_config_btn = QPushButton('Salvar configurações', self)
        self.save_config_btn.setFixedSize(115, 25)  # Ajusta o tamanho do botão
        self.save_config_btn.clicked.connect(self.save_config)

        self.update_btn = QPushButton('Atualizar', self)
        self.update_btn.clicked.connect(self.start_update)

        self.progress_bar = QProgressBar(self)
        self.progress_label = QLabel("Progresso: 0%")

        # Layouts
        src_layout = QHBoxLayout()
        src_layout.addWidget(self.src_input)
        src_layout.addWidget(self.src_browse_btn)

        dest_layout = QHBoxLayout()
        dest_layout.addWidget(self.dest_input)
        dest_layout.addWidget(self.dest_browse_btn)

        settings_layout = QHBoxLayout()
        settings_layout.addWidget(self.auto_update_checkbox)
        settings_layout.addWidget(self.save_config_btn)

        layout = QVBoxLayout()
        layout.addWidget(self.src_label)
        layout.addLayout(src_layout)
        layout.addWidget(self.dest_label)
        layout.addLayout(dest_layout)
        layout.addLayout(settings_layout)
        layout.addWidget(self.update_btn)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_label)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Carregar configurações
        self.load_config()
        self.center()

    def load_config(self):
        if os.path.exists('config.ini'):
            self.config.read('config.ini')
            self.src_input.setText(self.config.get('DEFAULT', 'source_directory', fallback=''))
            self.dest_input.setText(self.config.get('DEFAULT', 'destination_directory', fallback=''))
            self.auto_update_checkbox.setChecked(self.config.getboolean('DEFAULT', 'auto_update', fallback=False))
        if self.auto_update_checkbox.isChecked():
            self.start_update()

    def browse_src(self):
        dir_ = QFileDialog.getExistingDirectory(self, 'Selecionar Diretório de Origem')
        if dir_:
            self.src_input.setText(dir_)

    def browse_dest(self):
        dir_ = QFileDialog.getExistingDirectory(self, 'Selecionar Diretório de Destino')
        if dir_:
            self.dest_input.setText(dir_)

    def start_update(self):
        src_dir = self.src_input.text()
        dest_dir = self.dest_input.text()

        if not os.path.exists(src_dir) or not os.path.exists(dest_dir):
            QMessageBox.critical(self, 'Erro', 'Por favor, selecione diretórios válidos.')
            return

        # Salvar configurações
        self.config['DEFAULT'] = {
            'source_directory': src_dir,
            'destination_directory': dest_dir,
            'auto_update': self.auto_update_checkbox.isChecked()
        }
        with open('config.ini', 'w') as config_file:
            self.config.write(config_file)

        # Iniciar thread de atualização
        self.updater = FileUpdater(src_dir, dest_dir)
        self.updater.start_update.connect(self.initialize_progress)
        self.updater.update_progress.connect(self.update_progress)
        self.updater.finished_update.connect(self.finalize_update)
        self.updater.checking_file.connect(self.show_checking_file)
        self.updater.error_signal.connect(self.show_error_message)
        self.updater.start()

    @pyqtSlot(int)
    def initialize_progress(self, total_files):
        if total_files == 0:
            return

        self.progress_bar.setMaximum(total_files)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Progresso: 0%")

    @pyqtSlot(int, str)
    def update_progress(self, file_index, filename):
        self.progress_bar.setValue(file_index)
        percentage = (file_index / self.progress_bar.maximum()) * 100
        self.progress_label.setText(f"Progresso: {percentage:.2f}% - Transferindo: {filename}")

    @pyqtSlot(list, list, bool)
    def finalize_update(self, files_copied, files_failed, success):
        files_successfully_copied = [file for file in files_copied if file not in files_failed]

        if files_successfully_copied:
            reply = QMessageBox.question(self, 'Atualização Concluída',
                                         f'Arquivos transferidos: {len(files_successfully_copied)}\n\nDeseja ver a lista de arquivos transferidos?',
                                         QMessageBox.Yes | QMessageBox.No)

            if reply == QMessageBox.Yes:
                self.show_files_copied(files_successfully_copied, "Arquivos Transferidos")

        if files_failed:
            reply = QMessageBox.warning(self, 'Erros Durante a Atualização',
                                        f'Arquivos que falharam: {len(files_failed)}\n\nDeseja tentar novamente?',
                                        QMessageBox.Yes | QMessageBox.Cancel)

            if reply == QMessageBox.Yes:
                self.start_update()  # Isso irá iniciar a atualização novamente.
            elif reply == QMessageBox.Cancel:
                self.show_files_copied(files_failed, "Arquivos que Falharam")

        elif not files_failed and not files_successfully_copied:
            QMessageBox.information(self, 'Atualizado', 'Todos os arquivos já estão atualizados!')

    def show_files_copied(self, files, title):
        list_win = QMainWindow(self)
        list_win.setWindowTitle(title)
        list_win.setGeometry(200, 200, 600, 400)

        file_list = QTextEdit(list_win)
        file_list.setText("\n".join(files))
        file_list.setReadOnly(True)
        list_win.setCentralWidget(file_list)

        list_win.show()

    @pyqtSlot(str)
    def show_checking_file(self, filename):
        self.progress_label.setText(filename)

    def save_config(self):
        src_dir = self.src_input.text()
        dest_dir = self.dest_input.text()
        auto_update = self.auto_update_checkbox.isChecked()

        self.config['DEFAULT'] = {
            'source_directory': src_dir,
            'destination_directory': dest_dir,
            'auto_update': auto_update
        }
        with open('config.ini', 'w') as config_file:
            self.config.write(config_file)

        QMessageBox.information(self, 'Configurações', 'Configurações salvas com sucesso!')

    def center(self):
        qr = self.frameGeometry()  # obtém a geometria da janela principal
        cp = QDesktopWidget().availableGeometry().center()  # obtém o ponto central do display
        qr.moveCenter(cp)  # move o centro da janela principal para o ponto central
        self.move(qr.topLeft())  # move a janela principal para a posição

    def show_message(self, title, message, icon=QMessageBox.Information):
        """Mostrar uma mensagem para o usuário."""
        msg = QMessageBox(self)
        msg.setIcon(icon)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.exec_()

    def show_error_message(self, message):
        """Mostrar uma mensagem de erro para o usuário."""
        self.show_message("Erro na Atualização", message, icon=QMessageBox.Critical)


if __name__ == "__main__":
    import os
    os.environ["QT_EVENT_DISPATCHER"] = "windows"
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec_())
