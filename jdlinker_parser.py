import sys
import zipfile


__version = '1.0'


def print_error(error):
    length = len(error)
    print('=' * length)
    print(error)
    print('=' * length)


def could_not_find(javadoc_link, javadoc_page, javadoc_line):
    print('==========')
    print('Did not find: ' + javadoc_link)
    print('Page: ' + javadoc_page)
    print('On line: ' + javadoc_line)


def remove_generics(text):
    reformed_text = ''
    for split_text in text.split('<'):
        # Ignore lambdas
        if '->' in split_text:
            reformed_text += split_text
        # Else just remove the generics.
        elif '>' in split_text:
            reformed_text += split_text.partition('>')[2]
        else:
            reformed_text += split_text
    return reformed_text


# Require at least one jar argument. In python, the first argument is always the source file ran, so ignore that.
if len(sys.argv) == 1:
    print('Usage: \'python jdlinker_parser.py <source jars>\'')
    print('You may specify multiple source jars by specifying multiple arguments.')
    sys.exit(1)


print('Initializing jdlinker-parser.py version ' + __version + '!')
print('Attempting to read the javadoc dump file!')
try:
    dump_file = open('javadoc_dump.txt', 'r')
except FileNotFoundError:
    print_error('The javadoc_dump.txt file could not be found! Terminating...')
    sys.exit(1)


# We'll store the javadoc dump text as well as the jars into lists for when we're ready to iterate them.
javadoc_dump = []
jars = []


# For every line in the dump text file, store the relevant info into the dump list.
for line in dump_file:
    sectioned_line = line.split('=')
    javadoc_dump.append(sectioned_line[0] + '=' + sectioned_line[1] + '=' + sectioned_line[2])


# Now for every argument specified, iterate over it to get the jars.
for index, arg in enumerate(sys.argv):
    # If we are at the first index, ignore it. That is just the source file.
    if index == 0:
        continue

    print('\nAttempting to open file: \'' + arg + '\'')
    # Now we can use the python zipfile module to open the jar for us.
    try:
        jar = zipfile.ZipFile(sys.argv[index])
        print('File successfully opened!')
        jars.append(jar)
    except zipfile.BadZipFile:
        print_error('The specified file ' + arg + ' is not a zip file! Skipping...')
        continue
    except FileNotFoundError:
        print_error('The specified file ' + arg + ' could not be found! Skipping...')
        continue


# Now we will iterate through every javadoc link in the javadoc dump.
for javadoc_info in javadoc_dump:
    # Get the relevant javadoc info that we'll need.
    javadoc = javadoc_info.split('=')
    javadoc_link = javadoc[0]
    javadoc_page = javadoc[1]
    javadoc_line = javadoc[2]

    # Remove any generics if present.
    if '<' in javadoc_link:
        javadoc_link = remove_generics(javadoc_link)

    # We'll put the part after the hash into it's own variable.
    after_hash = ''
    if '#' in javadoc_link:
        after_hash = javadoc_link.partition('#')[2]
        # Now remove the part after the hash from here.
        javadoc_link = javadoc_link.partition('#')[0]

    # Get the part after the last dot.
    last_object = javadoc_link.rpartition('.')[2]
    # Get the part before the last dot, but the part after the dot from that.
    second_to_last = javadoc_link.rpartition('.')[0].rpartition('.')[2]

    # If this is a package, then we can scan it here.
    if not last_object[0].isupper():
        found_jar = False
        for jar in jars:
            try:
                jar.open(javadoc_link.replace('.', '/') + '/')
                found_jar = True
            except KeyError:
                pass
        if not found_jar:
            print('Could not find: ' + javadoc_link)
        continue

    # If the second to last object starts with a capital letter, assume that this is referencing an internal class.
    if second_to_last[0].isupper():
        is_internal = True
        package = javadoc_link.rpartition('.')[0].rpartition('.')[0].replace('.', '/') + '/'
    else:
        is_internal = False
        package = javadoc_link.rpartition('.')[0].replace('.', '/') + '/'

    file = None
    # Now iterate through each jar to find the one with the javadoc link.
    for jar in jars:
        if is_internal:
            try:
                file = jar.open(package + second_to_last + '.java')
                break
            except KeyError:
                pass
        else:
            try:
                file = jar.open(package + last_object + '.java')
                break
            except KeyError:
                pass

    if file:
        if after_hash:
            # Set some initial variables that will help determine of what type the after_hash is.
            before_parenthesis = ''
            in_parenthesis = ''
            is_field = False
            if '(' in after_hash:
                in_parenthesis = after_hash.partition('(')[2].partition(')')[0]
                before_parenthesis = after_hash.rpartition('(')[0]
            else:
                is_field = True

            found_method = False
            for line in file.readlines():
                # Decode to a string.
                line = line.decode('utf-8')

                # If the line is nothing, continue.
                if line is '\n':
                    continue

                # If the method is not even referenced in the line, continue.
                if before_parenthesis and before_parenthesis not in line:
                    continue
                # Else if this is a field and the field is not in the line, continue.
                elif is_field and after_hash not in line:
                    continue

                # Remove any generics in the line. We will ignore them.
                if '<' in line:
                    line = remove_generics(line)

                # If this is a field, then calculate for such.
                if is_field:
                    # Do our best to determine what possible fields the devs have created for us.
                    if after_hash + ',' in line or after_hash + '\n' in line or after_hash + ';' in line or after_hash\
                            + ' =' in line or after_hash + '(' in line:
                        found_method = True
                        break

                # If there is text in the parenthesis of after_hash, then we need to check for arguments.
                if in_parenthesis:
                    # For the line, split it on the parenthesis.
                    line_parenthesis = line.partition('(')[2].partition(')')[0]

                    # If there is a comma in the parenthesis, then assume multiple arguments.
                    if ',' in in_parenthesis:
                        # To make sure all of the arguments are there and in the correct order, we'll iterate through
                        # the line's arguments to ensure they all match up.
                        arg_index = 0
                        # For now, set this to True.
                        correct_args = True
                        for argument in in_parenthesis.split(','):
                            if not argument + ' ' + line_parenthesis.split(',')[arg_index]:
                                correct_args = False
                                break
                        if correct_args:
                            found_method = True
                            break
                    # Else, it is safe to calculate for just one.
                    else:
                        # BUT, if there is a comma in the LINE, then it is possible we hit the wrong method.
                        if ',' in line:
                            continue
                        arg_last_object = in_parenthesis.rpartition('.')[2]

                        # If the single argument is also in the parenthesis, then we can assume we found the correct
                        # method. Since we don't know the actual parameter name, we just check if the parameter object
                        # plus a space is there instead.
                        if arg_last_object + ' ' in line_parenthesis:
                            found_method = True
                            break
                # Else if there is nothing in the parenthesis, then we'll have to do our best to determine if this
                # is a method declaration. If it ends up accidentally hitting code instead of the method declaration,
                # then I suppose it's still fine, we can probably assume it still exists. :P
                elif (' ' + after_hash + ' ' in line or ' ' + after_hash + ';' in line) and 'return' not in line:
                    found_method = True
                    break
            if not found_method:
                if is_internal:
                    could_not_find(second_to_last + '.' + last_object + '#' + after_hash, javadoc_page,
                                   javadoc_line)
                else:
                    could_not_find(last_object + '#' + after_hash, javadoc_page, javadoc_line)
    else:
        if is_internal:
            could_not_find(package + second_to_last + '.java', javadoc_page, javadoc_line)
        else:
            could_not_find(package + last_object + '.java', javadoc_page, javadoc_line)

# Now close any open jars.
for jar in jars:
    jar.close()


print('\njdlinker_parser.py has completed.')
