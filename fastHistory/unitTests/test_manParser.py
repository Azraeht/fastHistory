import inspect
import logging
from unittest import TestCase

import os

from parser.manParser import ManParser


class TestManParser(TestCase):
    """
    test class for the man parser
    """

    log_file_name = "data/test_manParser.log"

    def setUp(self):
        """
        setup absolute log path and log level
        :return:
        """
        current_path = os.path.dirname(os.path.realpath(__file__)) + "/../"
        self.log_path = current_path + self.log_file_name

        logging.basicConfig(filename=self.log_path, level=logging.DEBUG)

    def test_load_man_page(self):
        """
        get the meaning ('name' field) from the man page
        :return:
        """
        self._set_text_logger()
        parser = ManParser()

        test_strings = [
            "tar",
            "ls",
            "netstat"
        ]
        for t in test_strings:
            self.assertTrue(parser.load_man_page(t))
            meaning = parser.get_cmd_meaning()
            self.assertIsNotNone(meaning)

    def test_get_cmd_meaning(self):
        self._set_text_logger()
        parser = ManParser()

        test_string = [
            "tar",
            "ls",
            "netstat",
            "wget",
            "grep"
        ]
        for t in test_string:
            logging.info("test: " + str(t))
            self.assertTrue(parser.load_man_page(t))
            meaning = parser.get_cmd_meaning()
            self.assertTrue(meaning)
            logging.info(meaning)

    def test_get_flag_meaning(self):
        self._set_text_logger()
        parser = ManParser()

        test_string = [
            ["tar", "-d"],
            ["ls", "-l"],
            ["netstat", "-a"],
            ["netstat", "-n"],
            ["lsof", "-i"],
            ["wget", "--quiet"]
        ]
        for t in test_string:
            logging.info("test: " + str(t))
            self.assertTrue(parser.load_man_page(t[0]))
            flag_meaning = parser.get_flag_meaning(t[1])
            self.assertTrue(flag_meaning)
            logging.info("flag meaning: " + str(flag_meaning))

    def _set_text_logger(self):
        """
        set global setting of the logging class and print (dynamically) the name of the running test
        :return:
        """
        logging.info("*" * 30)
        # 0 is the current function, 1 is the caller
        logging.info("Start test '" + str(inspect.stack()[1][3]) + "'")
