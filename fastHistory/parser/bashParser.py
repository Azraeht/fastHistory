import logging

from parser import bashlex
from parser.manParser import ManParser


class BashParser(object):
    """
    Class to parse bash commands and handle flags
    """

    logFile = "/home/mart/Desktop/file.log"

    CMD_NODE_TYPE_CMD = "command"
    CMD_NODE_TYPE_WORD = "word"
    CMD_NODE_TYPE_LIST = "list"
    CMD_NODE_TYPE_OPERATOR = "operator"
    CMD_NODE_TYPE_PIPELINE = "pipeline"
    CMD_NODE_TYPE_PIPE = "pipe"
    CMD_NODE_TYPE_COMPOUND = "compound"

    INDEX_VALUE = 0
    INDEX_MEANING = 1

    INDEX_CMD = 0
    INDEX_FLAGS = 1

    WORD_TO_IGNORE = ["sudo", "true", "false"]

    def __init__(self):
        self.logger = logging.getLogger(self.logFile)
        self.logger.setLevel(logging.INFO)

    def get_flags_from_bash_node(self, bash_node, result, cmd_main=None, first_cmd=False):
        self.logger.debug("result: " + str(result))
        # check if node is a list
        if type(bash_node) == list:
            for i in bash_node:
                self.get_flags_from_bash_node(i, result)
        elif hasattr(bash_node, "list"):
            for i in bash_node.list:
                self.get_flags_from_bash_node(i, result)
        elif hasattr(bash_node, "kind"):
            # check if node is a command
            if bash_node.kind == self.CMD_NODE_TYPE_CMD:
                items_len = len(bash_node.parts)
                if items_len > 0 and bash_node.parts[0].kind == self.CMD_NODE_TYPE_WORD and bash_node.parts[0].word in self.WORD_TO_IGNORE:
                    self.logger.debug("ignore word: " + bash_node.parts[0].word)
                    bash_node.parts = bash_node.parts[1:]

                for i in range(len(bash_node.parts)):
                    if i == 0:
                        cmd_main = self.get_flags_from_bash_node(bash_node.parts[i], result, first_cmd=True)
                    else:
                        self.get_flags_from_bash_node(bash_node.parts[i], result, cmd_main=cmd_main, first_cmd=False)
            # check if node is a word
            elif bash_node.kind == self.CMD_NODE_TYPE_WORD:
                self.logger.debug("bash_node.word word: " + bash_node.word)
                if first_cmd:
                    found = False
                    for item in result:
                        if item[self.INDEX_CMD][self.INDEX_VALUE] == bash_node.word:
                            found = True
                            break
                    if not found:
                        result.append([[bash_node.word, None], []])
                    return bash_node.word
                else:
                    if cmd_main is not None:
                        for item in result:
                            if item[self.INDEX_CMD][self.INDEX_VALUE] == cmd_main:
                                found = False
                                for flag in item[self.INDEX_FLAGS]:
                                    if flag[self.INDEX_VALUE] == bash_node.word:
                                        found = True
                                        break
                                if not found:
                                    item[self.INDEX_FLAGS].append([bash_node.word, None])
                                break
                    else:
                        self.logger.error("error cmd main null")

                self.logger.debug("word value: " + bash_node.word)
            elif getattr(bash_node, "parts", None):
                # check if node has parts
                for i in bash_node.parts:
                    self.get_flags_from_bash_node(i, result)
            else:
                self.logger.debug("other kind: " + bash_node.kind + "\n")
        else:
            self.logger.debug("unknown obj: " + str(bash_node) + "\n")

    def get_flags(self, bash_node, result, cmd_main=None, first_cmd=False):

        if type(bash_node) == list:
            for i in bash_node:
                self.get_flags(i, result)
        else:
            self.logger.debug("kind: " + bash_node.kind)
            if bash_node.kind == self.CMD_NODE_TYPE_LIST:
                for i in bash_node.parts:
                    self.get_flags(i, result)
            elif bash_node.kind == self.CMD_NODE_TYPE_COMPOUND:
                for i in bash_node.list:
                    self.get_flags(i, result)
            elif bash_node.kind == self.CMD_NODE_TYPE_PIPELINE:
                self.logger.debug("pipeline: " + str(bash_node))
                for i in bash_node.parts:
                    self.get_flags(i, result)
            elif bash_node.kind == self.CMD_NODE_TYPE_CMD:
                items_len = len(bash_node.parts)
                if items_len > 0 and bash_node.parts[0].kind == self.CMD_NODE_TYPE_WORD and bash_node.parts[0].word in self.WORD_TO_IGNORE:
                    self.logger.debug("ignore word: " + bash_node.parts[0].word)
                    bash_node.parts = bash_node.parts[1:]

                for i in range(len(bash_node.parts)):
                    if i == 0:
                        cmd_main = self.get_flags(bash_node.parts[i], result, first_cmd=True)
                    else:
                        self.get_flags(bash_node.parts[i], result, cmd_main=cmd_main, first_cmd=False)
            elif bash_node.kind == self.CMD_NODE_TYPE_WORD:
                if first_cmd:
                    found = False
                    for item in result:
                        if item[0] == bash_node.word:
                            found = True
                            break
                    if not found:
                        result.append([bash_node.word, []])
                    return bash_node.word
                else:
                    if cmd_main is not None:
                            for item in result:
                                if item[0] == cmd_main:
                                    found = False
                                    for flag in item[1]:
                                        if flag == bash_node.word:
                                            found = True
                                            break
                                    if not found:
                                        item[1].append(bash_node.word)
                                    break
                    else:
                        self.logger.error("error cmd main null")

                self.logger.debug("word value: " + bash_node.word)
            elif bash_node.kind in self.CMD_NODE_TYPE_OPERATOR:
                self.logger.debug("OP: " + str(bash_node.op))
            elif bash_node.kind in self.CMD_NODE_TYPE_PIPE:
                self.logger.debug("PIPE: " + str(bash_node.pipe))
            else:
                print("unknown: " + bash_node.kind + "\n")
                self.logger.debug("unknown: " + bash_node.kind + "\n")

    @staticmethod
    def decompose_possible_concatenated_flags(flag_string):
        """
        Given a possible concatenated flag string it return an array with all the flags decomposed
        NOTE: flags like "--help" must not be decomposed

        :param flag_string:     example: -lsv
        :return:                example: ['-l','-s','-v']
        """
        flags = []
        flag_dash = '-'
        # "-" ok , "--" not
        if len(flag_string) >= 2 and flag_string[0] == flag_dash and flag_string[1] != flag_dash:
            flag_string = flag_string[1:]
            flag_len = len(flag_string)
            if flag_len == 1:
                # basic flag (example: -l)
                flags.append(flag_dash + flag_string)
            elif flag_len > 1:
                # combined flags (example: -lsv)
                for c in flag_string:
                    if str(flag_dash + c) not in flags:
                        flags.append(flag_dash + c)
            else:
                # '-' case
                pass
        else:
            # only flags which start with '-' are currently supported
            # possible improvement: support generic flags (such as "git add ..")
            pass
        return flags

    @staticmethod
    def load_data_for_info_from_man_page(cmd_text):
        """
        retrieve info about the currently selected cmd from the man page

        :param cmd_text:    the bash cmd string
        :return:            a structured list with info for each cmd and flags
        """
        # here the man search and parse
        parser = BashParser()
        # create a result var to fill
        flags_for_info_cmd = list()
        # parse the cmd string
        cmd_parsed = bashlex.parse(cmd_text)
        # find all flags for each commands
        parser.get_flags_from_bash_node(cmd_parsed, flags_for_info_cmd)
        # for each cmd and flag find the meaning from the man page
        man_parsed = ManParser()
        for item in flags_for_info_cmd:
            cmd_main = item[BashParser.INDEX_CMD]
            cmd_flags = item[BashParser.INDEX_FLAGS]
            if man_parsed.load_man_page(cmd_main[BashParser.INDEX_VALUE]):
                # save cmd meaning
                cmd_main[BashParser.INDEX_MEANING] = man_parsed.get_cmd_meaning()
                # cmd meaning found in the man page
                if cmd_main[BashParser.INDEX_MEANING]:
                    cmd_flags_updated = list()
                    for flag_i in range(len(cmd_flags)):
                        flag = cmd_flags[flag_i]
                        flag[BashParser.INDEX_MEANING] = man_parsed.get_flag_meaning(flag[BashParser.INDEX_VALUE])
                        # if flag found in the man page
                        if flag[BashParser.INDEX_MEANING]:
                            cmd_flags_updated.append(flag)
                        else:
                            # try to check if flag is concatenated
                            conc_flags = BashParser.decompose_possible_concatenated_flags(flag[BashParser.INDEX_VALUE])
                            for conc_flag in conc_flags:
                                conc_flag_meaning = man_parsed.get_flag_meaning(conc_flag)
                                cmd_flags_updated.append([conc_flag, conc_flag_meaning])
                    # set the updated flags as new list of flags, the old list is deleted
                    item[BashParser.INDEX_FLAGS] = cmd_flags_updated
        return flags_for_info_cmd
