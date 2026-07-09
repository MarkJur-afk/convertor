import os

class BaseConverter:
    """
    Базовый класс для всех конвертеров форматов.
    Каждая конкретная реализация должна наследоваться от этого класса и реализовывать метод _do_convert.
    """
    def __init__(self, input_path: str, output_path: str):
        self.input_path = input_path
        self.output_path = output_path

    def convert(self, progress_callback=None, check_cancel=None):
        """
        Запускает процесс конвертации с поддержкой прогресса и отмены.
        
        :param progress_callback: Функция, принимающая float от 0.0 до 100.0
        :param check_cancel: Функция без параметров, возвращающая True, если нужно прервать операцию
        """
        if not os.path.exists(self.input_path):
            raise FileNotFoundError(f"Исходный файл не найден: {self.input_path}")
            
        self._do_convert(progress_callback, check_cancel)

    def _do_convert(self, progress_callback, check_cancel):
        """
        Метод должен быть переопределен в дочерних классах.
        """
        raise NotImplementedError("Метод _do_convert должен быть переопределен в дочернем классе.")
