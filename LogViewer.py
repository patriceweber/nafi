
import os
import re
import sys

from re import RegexFlag

import argparse


#===============================================================================
#                        Begin parsing command line options
#===============================================================================

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('-l', '--log', nargs=1, metavar='[log file]', default=None, help='Loads log file')
parser.add_argument('-p', '--process', nargs=1, metavar='[process name]', default=None, help='filering by process name')
parser.add_argument('-t', '--tags', nargs=1, metavar='[INFO, DEBUG, WARNING, CRITICAL, ERROR]', default=None, help='filering by tag name')

args = parser.parse_args()

if len(sys.argv) == 1:
    print('\n')
    parser.print_help()
    exit(0)

if args.log is None:
    parser.print_help()
    exit(0)

# Verify the configuration file exists (default or from command line)
if args.log.__class__.__name__ == 'list':
    flog = args.log[0]
else:
    flog = args.log

basename = os.path.basename(flog)

if basename == flog:
    # try relative path
    if not os.path.isfile(os.path.join(os.getcwd(), flog)):
        #logger.critical('Config file not found: %s', os.path.join(os.getcwd(), flog))
        exit(1)
else:
    if not os.path.isfile(flog):
        #logger.critical('Config file not found: %s', flog)
        exit(1)


if args.tags is None and args.process is None:

    with open(flog) as f:
        content = f.readlines()

    # Remove whitespace characters like `\n` at the end of each line
    content = [x.strip() for x in content]

    print('\n')
    for line in content:
        print(line)

    exit(0)


if args.tags:
    if args.tags.__class__.__name__ == 'list':
        tags = tuple(args.tags[0].split(','))
    else:
        tags = tuple(args.tags.split('|'))

    for tag in tags:
        if tag not in ('DEBUG', 'INFO', 'CRITICAL', 'WARNING', 'ERROR'):
            print('\n')
            print('Unknown logfile tag: {0}'.format(tag))
            print(' ')
            parser.print_help()
            exit(0)

process = None

if args.process:
    if args.process.__class__.__name__ == 'list':
        process = args.process[0]
    else:
        process = args.process

# Assemble search pattern from tag list
if process is None:
    pattern = '|'.join([r'(\[%s\])']*len(tags)) % tags
else:
    tmp = '%s: ' % process
    pattern = '|'.join([tmp + r'(\[%s\])']*len(tags)) % tags


with open(flog) as f:
    content = f.readlines()

# Remove whitespace characters like `\n` at the end of each line
content = [x.strip() for x in content]

filtered = [x for x in content if re.search(pattern, x, flags=RegexFlag.IGNORECASE)]

print('\n')
for line in filtered:
    print(line)


exit(0)
