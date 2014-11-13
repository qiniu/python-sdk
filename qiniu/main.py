#! /usr/bin/env python
# -*- coding: utf-8 -*-

import argparse

from qiniu import etag


def main():
    parser = argparse.ArgumentParser(prog='qiniu')
    sub_parsers = parser.add_subparsers()

    parser_etag = sub_parsers.add_parser(
        'etag', description='calculate the etag of the file', help='etag [file...]')
    parser_etag.add_argument(
        'etag_files', metavar='N', nargs='+', help='the file list for calculate')

    args = parser.parse_args()

    if args.etag_files:
        r = [etag(file) for file in args.etag_files]
        if len(r) == 1:
            print(r[0])
        else:
            print(' '.join(r))

if __name__ == '__main__':
    main()
