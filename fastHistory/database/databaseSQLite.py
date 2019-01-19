import sqlite3
import logging
import os
import time

from database.databaseCommon import DatabaseCommon


class DatabaseSQLite(object):

    TABLE_NAME = "history"
    COLUMN_CMD = "cmd"
    COLUMN_DESCRIPTION = "description"
    COLUMN_TAGS = "tags"

    CHAR_TAG = "#"
    CHAR_DESCRIPTION = "@"
    CHAR_DIVIDER = " "
    EMPTY_STRING = ""
    EMPTY_STRING_TUPLE = ('', )

    MAX_NUMBER_OF_WORDS_TO_COMBINE = 4

    _DATABASE_TABLE_NAME = "history"
    _DATABASE_STRUCTURE = """
    command  TEXT,
    description TEXT,
    tags TEXT,
    counter INTEGER,
    date INTEGER,
    synced TINYINT
    """

    def __init__(self, project_path, db_relative_path, old_db_relative_paths, delete_all_data_from_db=False):
        """
        check if database file exit, connect to it and initialize it

        :param project_path:            the current path of the project
        :param db_relative_path:        the relative path of the database file
        :param old_db_relative_paths:    the array of relative paths of (possible) database files to migrate
        :param delete_all_data_from_db:   if true the db file is delete (ONLY for test purposes)
        """
        self.project_path = project_path
        self.db_relative_path = db_relative_path
        if delete_all_data_from_db:
            self.reset_entire_db()
        self._connect_db(old_db_relative_paths)

    def _connect_db(self, old_db_relative_paths):
        """
        connect to db and create it if it does not exit

        :return:
        """
        init = not os.path.isfile(self.project_path + self.db_relative_path)

        self.conn = sqlite3.connect(self.project_path + self.db_relative_path)
        self.cursor = self.conn.cursor()
        if init:
            self._create_db()
            self.save_changes()

            if old_db_relative_paths is not None:
                # this will loop from the newest to the oldest db
                for old_db in old_db_relative_paths:
                    if self._automatic_db_migration(old_db[0], old_db[1]) is True:
                        logging.info("successfully migrated data from old database (%s) to new one (%s)" %
                                     (self.project_path + old_db[1], self.project_path + self.db_relative_path))
                        # delete old db
                        try:
                            os.remove(self.project_path + old_db[1])
                            logging.info("old database file deleted")
                        except OSError or ValueError:
                            logging.error("file delete fail. please manually delete the old database file: %s" %
                                          self.project_path + old_db[1])

    def _automatic_db_migration(self, old_db_type, old_db_relative_path):
        """
        check if old db file exists and move data from old to new db with no user interaction
        this is needed when the database file position or structure changed (between project versions)

        for each future change of the database a new type of database will be added to this function
        to be able to migrate data from any version to any version

        :param old_db_type:             type of the old database, this value is used like a version identification
        :param old_db_relative_path:    relative path of old database file
        :return:                        true if an the old database was found and correctly migrated, false otherwise
        """
        try:
            if old_db_type == 0:
                """"
                db structure of db type 0
                
                TABLE history 
                (
                    command  TEXT,
                    counter BIGINT,
                    description TEXT,
                    tags TEXT
                )
                """
                if os.path.isfile(self.project_path + old_db_relative_path):
                    migration_success = True
                    # connect to old db
                    tmp_conn_old = sqlite3.connect(self.project_path + old_db_relative_path)
                    tmp_cursor_old = tmp_conn_old.cursor()

                    # get all value from old db
                    tmp_cursor_old.execute("SELECT command, counter, description, tags FROM history")
                    old_db_data = tmp_cursor_old.fetchall()
                    for item in old_db_data:
                        old_cmd = item[0]
                        old_counter = item[1]
                        old_desc = item[2]
                        old_tags = self._tags_string_to_array(item[3])
                        old_date = 0  # the date was not available therefore we select the oldest date possible

                        if not self.add_element(old_cmd,
                                                description=old_desc,
                                                tags=old_tags,
                                                counter=old_counter,
                                                date=old_date):
                            migration_success = False

                    tmp_conn_old.close()
                    return migration_success
                else:
                    logging.debug("database migration - database type %d not found" % old_db_type)
                    return False
            else:
                logging.error("database migration - unknown old database: %s" % old_db_relative_path)
                return False
        except Exception as e:
            logging.error("database migration - error: %s" % str(e))
            return False

    def save_changes(self):
        """
        after each change to the db a save must be done

        :return:
        """
        self.conn.commit()

    def reset_entire_db(self):
        """
        for debug and test purposes delete the db file

        :return:
        """
        if os.path.exists(self.project_path + self.db_relative_path):
            os.remove(self.project_path + self.db_relative_path)

    def close(self):
        """
        close connection to db

        :return:
        """
        self.conn.close()

    def _create_db(self):
        """
        create table to store commands
        Note: this table results to be the most efficient tested structure to fast filter data
        the "tags" column is composed by the concatenation of single 'tag' string separated by a #
        because during the search procedure the # cannot be used this will result an optimized string search
        without false positives
        example     command, counter, description, tags
                    ls 1     2        info         #file#list#disk
                    srm -r   1        delete file  #secure#remove

                search with filter value = "list"
                result:
                    ls 1     2        info         #file#list#disk

        :return:
        """
        logging.info("database - create database")
        self.cursor.execute("CREATE TABLE %s ( %s )" % (self._DATABASE_TABLE_NAME, self._DATABASE_STRUCTURE))

        # note: sqlite automatically adds a column called "rowID"
        # the "rowID" value is a 64-bit signed integers
        # REAL is used because it has the longest time range

    def get_all_data(self):
        self.cursor.execute("SELECT * FROM history ")
        return self.cursor.fetchall()

    def get_last_n_filtered_elements(self, generic_filters=None, description_filters=None, tags_filters=None, n=50):
        """
        get filtered data from db

        :param generic_filters:        array of words used to filter cmd, descriptions and tags
        :param description_filters:    array of words used to filter descriptions
        :param tags_filters:           array of words used to filter tags
        :param n:                      max number of rows returned
        :return:                       filtered data (array of array [command, description, tags])
        """

        if generic_filters is not None and len(generic_filters) > self.MAX_NUMBER_OF_WORDS_TO_COMBINE:
            # TODO show feedback to user when this kind of search is done
            combinations_generic_filters = [tuple(generic_filters)]
        else:
            combinations_generic_filters = DatabaseCommon.get_all_unique_combinations(generic_filters)

        if description_filters is not None and len(description_filters) > self.MAX_NUMBER_OF_WORDS_TO_COMBINE:
            combinations_description_filters = [tuple(description_filters)]
        else:
            combinations_description_filters = DatabaseCommon.get_all_unique_combinations(description_filters)

        parameters = ()
        where_needed = True

        query = "SELECT command, description, tags " \
                "FROM history "

        if combinations_generic_filters is not None and len(combinations_generic_filters) > 0:
            if where_needed:
                query += " WHERE ("
                where_needed = False

            or_needed = False
            for combination in combinations_generic_filters:
                if or_needed:
                    query += " OR "
                else:
                    or_needed = True

                pattern = '%' + '%'.join(combination) + '%'
                # a divider is used to avoid the corner case where a word matches only
                # because of the concatenation of different columns
                query += "(command || ? || description || ? || tags LIKE ? ) "
                parameters += (self.CHAR_DIVIDER, self.CHAR_DIVIDER, pattern, )
            query += ") "

        if combinations_description_filters is not None and len(combinations_description_filters) > 0:
            if where_needed:
                query += " WHERE ("
                where_needed = False
            else:
                query += " AND ("

            or_needed = False
            for desc_combination in combinations_description_filters:
                if or_needed:
                    query += " OR "
                else:
                    or_needed = True
                if desc_combination == DatabaseSQLite.EMPTY_STRING_TUPLE:
                    query += "description <> '' "
                    parameters += ()
                else:
                    desc_pattern = '%' + '%'.join(desc_combination) + '%'
                    query += "description LIKE ? "
                    parameters += (desc_pattern, )
            query += ") "

        if tags_filters is not None and len(tags_filters) > 0:
            if where_needed:
                query += " WHERE ("
            else:
                query += " AND ("

            and_needed = False
            for tag_filter in tags_filters:
                if and_needed:
                    query += "AND "
                else:
                    and_needed = True

                if tag_filter == DatabaseSQLite.EMPTY_STRING:
                    query += "tags <> '' "
                    parameters += ()
                else:
                    pattern = "%" + tag_filter + "%"
                    query += "tags LIKE ? "
                    parameters += (pattern, )
            query += ") "

        query += "ORDER BY rowid DESC LIMIT ?"
        parameters += (n,)

        # execute query
        self.cursor.execute(query, parameters)

        logging.debug("database:search - query: " + query)
        logging.debug("database:search - parameters: " + str(parameters))

        return DatabaseCommon.cast_return_type(self.cursor.fetchall())

    def add_element(self, cmd, description=None, tags=None, counter=0, date=None, synced=0):
        """
        insert a new element in the database,
        if it already in the db just increase the counter
        if the description is different it updates it
        if there are new tags it updates the tags string

        :param cmd:             bash command
        :param description:     description
        :param tags:            array of tag
        :param counter:         usage counter
        :param date:            date of last change (UTC time in Epoch timestamp)
        :param synced:          boolean for future usage

        :return:                true if the command has been store successfully
        """

        try:
            # remove whitespaces on the left and right
            cmd = cmd.strip()

            if date is None:
                date = self._get_time_now()

            # check if description and tags contains an illegal char (@ or #)
            if description is not None and (self.CHAR_TAG in description or self.CHAR_DESCRIPTION in description):
                logging.error("database:add element - description contains illegal char " +
                              self.CHAR_DESCRIPTION + ": " + description)
                return False
            if tags is not None and type(tags) == list:
                for tag in tags:
                    if self.CHAR_TAG in tag or self.CHAR_DESCRIPTION in tag:
                        logging.error("database:add element - tags contains illegal char " +
                                      self.CHAR_DESCRIPTION + ": " + tag)
                        return False

            logging.debug("database:add element - add command: " + str(cmd))
            logging.debug("database:add element - tags: " + str(tags))
            logging.debug("database:add element - description: " + str(description))
            logging.debug("database:add element - counter: " + str(counter))
            logging.debug("database:add element - date: " + str(date))
            logging.debug("database:add element - synced: " + str(synced))

            self.cursor.execute("SELECT rowid, description, tags, counter FROM history WHERE command=?", (cmd,))
            matches = self.cursor.fetchall()
            matches_number = len(matches)
            if matches_number == 0:
                if description is None:
                    description = ""
                if tags is None:
                    tags_str = ""
                else:
                    tags_str = self._tag_array_to_string(tags)
                self.cursor.execute("INSERT INTO history values (?, ?, ?, ?, ?, ?)",
                                    (cmd,
                                     description,
                                     tags_str,
                                     counter,
                                     date,
                                     synced
                                     ))
                logging.debug("database:add element - added NEW")
            elif matches_number == 1:
                match = matches[0]
                # get old values
                match_id = match[0]
                match_desc = match[1]
                match_tags_str = match[2]
                match_counter = int(match[3])
                # match_date = int(match[4])

                # set new counter
                new_counter = match_counter + 1
                # set new description
                if description is not None and description is not "" and description != match_desc:
                    if match_desc is "":
                        new_description = description
                    else:
                        # concatenate old and new description
                        new_description = description + ". " + match_desc
                else:
                    new_description = match_desc
                # set new tags list
                if tags is not None and type(tags) == list and len(tags) > 0:
                    update_tags = False
                    match_tags = self._tags_string_to_array(match_tags_str)
                    for tag in tags:
                        if tag not in match_tags and tag != "":
                            # new tag
                            match_tags.append(tag)
                            update_tags = True
                    if update_tags:
                        new_tags_str = self._tag_array_to_string(match_tags)
                    else:
                        new_tags_str = match_tags_str
                else:
                    new_tags_str = match_tags_str

                # delete old row
                self.cursor.execute("DELETE FROM history WHERE rowid=?", (match_id,))

                logging.debug("database:add element - new_tags_str: " + str(new_tags_str))
                # create new row which will have the highest rowID (last used command)

                self.cursor.execute("INSERT INTO history values (?, ?, ?, ?, ?, ?)", (
                    (cmd,
                     new_description,
                     new_tags_str,
                     new_counter,
                     date,
                     synced
                     )))
                logging.debug("database:add element - command updated: " + cmd)
            else:
                logging.error("database:add element - command entry is not unique: " + cmd)
                return False

            self.save_changes()
            return True
        except Exception as e:
            logging.error("database:add element - thrown an error: %s" % str(e))
            return False

    def update_tags_field(self, cmd, tags):
        """
        update tags field
        first get the row id and then update the tag list (and date!) of the found command

        :param cmd:             command to update
        :param tags:            new tags array
        :return:                True is the database was successfully changed, False otherwise
        """
        try:
            if tags is None:
                logging.error("database - update_tags_field: tags is null")
                return False

            logging.debug("database - update_tags_field: " + str(cmd) + " with " + str(tags))
            self.cursor.execute("SELECT  rowid, tags, date FROM history WHERE command=?", (cmd,))
            matches = self.cursor.fetchall()
            matches_number = len(matches)
            if matches_number == 1:
                match = matches[0]
                item_row_id = match[0]
                item_tags_str = match[1]
                item_date = match[2]

                new_tags_str = self._tag_array_to_string(tags)
                new_date = self._get_time_now()
                if item_tags_str != new_tags_str:
                    # update tags
                    self.cursor.execute("UPDATE history SET tags=?, date=? WHERE rowid=?", (
                        new_tags_str,
                        new_date,
                        item_row_id))
                    self.save_changes()
                    return True
                else:
                    logging.debug("database - update_tags_field - no changed")
                    return True
            else:
                logging.error("database - update_tags_field - fail because of no matched command")
                return False
        except Exception as e:
            logging.error("database - update_tags_field error: %s" % str(e))
            return False

    def update_description_field(self, cmd, description):
        """
        update description field
        first get the row id and then update the description (and date!) of the found command

        :param cmd:             command to update
        :param description:     new description
        :return:                True is the database was successfully changed, False otherwise
        """
        try:
            if description is None:
                return False

            logging.debug("database - update_description_field: " + str(cmd) + " with " + str(description))
            self.cursor.execute("SELECT  rowid, description, date FROM history WHERE command=?", (cmd,))
            matches = self.cursor.fetchall()
            matches_number = len(matches)
            if matches_number == 1:
                match = matches[0]
                item_row_id = match[0]
                item_desc_str = match[1]
                item_date = match[2]

                new_date = self._get_time_now()
                if item_desc_str != description:
                    # update tags
                    self.cursor.execute("UPDATE history SET description=?, date=? WHERE rowid=?", (
                        description,
                        new_date,
                        item_row_id))
                    self.save_changes()
                    return True
                else:
                    return True
            else:
                logging.error("database - update_description_field - fail because of no matched command")
                return False
        except Exception as e:
            logging.error("database - update_description_field error: %s" % str(e))
            return False

    def update_position_element(self, cmd):
        """
        when a command is selected two changes are made:
            - counter increased (+1)
            - the row id is update with a new one. this is done to move the selected cmd on the top (or botton,
              it depends on the point of view) and to have a faster search the next time

        :param cmd:     command to update
        :return:        True is the database was successfully changed, False otherwise
        """
        try:
            logging.debug("database - update_position_element: " + str(cmd))
            self.cursor.execute("SELECT  rowid, description, tags, counter, date, synced FROM history WHERE command=?", (cmd,))
            matches = self.cursor.fetchall()
            matches_number = len(matches)
            if matches_number == 1:
                match = matches[0]
                matched_id = match[0]
                # delete old row
                self.cursor.execute("DELETE FROM history WHERE rowid=?", (matched_id,))
                # create new row which will have the highest rowID (last used command)
                self.cursor.execute("INSERT INTO history values (?, ?, ?, ?, ?, ?)", (
                    cmd,
                    match[1],
                    match[2],
                    int(match[3]) + 1,
                    match[4],
                    match[5]))
                self.save_changes()
                return True
            else:
                logging.error("database - update_position_element - fail because of no matched command")
                return False
        except Exception as e:
            logging.error("database - update_position_element error: %s" % str(e))
            return False

    def remove_element(self, cmd):
        """
        delete specific command from database

        :param cmd:     cmd to delete
        :return:        true is successfully deleted, false otherwise
        """
        try:
            logging.info("delete command: " + str(cmd))
            if cmd is None:
                logging.error("remove_element: " + "cmd is None")
                return False
            # remove whitespaces on the left and right
            cmd = cmd.strip()
            if len(cmd) == 0:
                logging.error("remove_element: " + "cmd is empty")
                return False

            # delete item
            self.cursor.execute("DELETE FROM history WHERE  command=?", (cmd,))
            self.save_changes()
            logging.debug("delete completed")
            return True
        except Exception as e:
            logging.error("database - remove_element error: %s" % str(e))
            return False

    def _tags_string_to_array(self, tags_string):
        """
        given the string of tags form the db it split the tags word and put it into an array
        if the string is empty and empty array is returned

        :param tags_string:     #tag1#tag2#tag3
        :return:                ["tag1","tag2","tag3"]
        """
        if type(tags_string) is not str:
            logging.error("database - _tags_string_to_array - wrong type")
            return None
        if tags_string == "":
            return []
        tags = tags_string.split(self.CHAR_TAG)
        if len(tags) >= 2:
            # remove first always empty value
            tags = tags[1:]
            return tags
        else:
            return []

    def _tag_array_to_string(self, tags):
        """
        given a tags array it returns the tags string to store it into the db
        note: empty tag are not stored

        :param tags:
        :return:
        """
        if type(tags) is not list:
            logging.error("database - _tag_array_to_string - wrong type")
            return None

        tags_string = ""
        for tag in tags:
            if len(tag) > 0:
                tags_string += self.CHAR_TAG + tag
        return tags_string

    def _get_time_now(self):
        """
        https://www.epochconverter.com/

        :return: unix epoch time
        """
        return int(time.time())