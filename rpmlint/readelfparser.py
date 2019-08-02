from itertools import dropwhile, takewhile
import re
import subprocess


class ElfSection:
    """
    A simple wrapper representing one ELF section.
    """
    def __init__(self, name, size):
        self.name = name
        self.size = int(size, 16)


class ElfProgramHeader:
    """
    A simple wrapper representing one ELF program header.
    """
    def __init__(self, name, flags):
        self.name = name
        self.flags = flags.replace(' ', '')


class ElfDynamicSection:
    """
    A simple wrapper representing one ELF dynamic section entry.
    """
    def __init__(self, key, value):
        self.key = key
        self.value = value


class ElfSymbol:
    """
    A simple wrapper representing one ELF symbol.
    """
    def __init__(self, type, bind, visibility, name):
        self.type = type
        self.bind = bind
        self.visibility = visibility
        self.name = name


class ElfSectionInfo:
    """
    Class contains information about ELF sections of an ELF file. The information
    is get with the following command line: readelf -WS.

    Output example:

    There are 12 section headers, starting at offset 0x268:

    Section Headers:
      [Nr] Name              Type            Address          Off    Size   ES Flg Lk Inf Al
      [ 0]                   NULL            0000000000000000 000000 000000 00      0   0  0
      [ 1] .text             PROGBITS        0000000000000000 000040 000015 00  AX  0   0  1
      [ 2] .rela.text        RELA            0000000000000000 0001d8 000018 18   I  9   1  8
      [ 3] .data             PROGBITS        0000000000000000 000055 000000 00  WA  0   0  1
      [ 4] .bss              NOBITS          0000000000000000 000055 000000 00  WA  0   0  1
      [ 5] .comment          PROGBITS        0000000000000000 000055 000041 01  MS  0   0  1
      [ 6] .note.GNU-stack   PROGBITS        0000000000000000 000096 000000 00      0   0  1
      [ 7] .eh_frame         PROGBITS        0000000000000000 000098 000038 00   A  0   0  8
      [ 8] .rela.eh_frame    RELA            0000000000000000 0001f0 000018 18   I  9   7  8
      [ 9] .symtab           SYMTAB          0000000000000000 0000d0 0000f0 18     10   8  8
      [10] .strtab           STRTAB          0000000000000000 0001c0 000011 00      0   0  1
      [11] .shstrtab         STRTAB          0000000000000000 000208 000059 00      0   0  1
    Key to Flags:
      W (write), A (alloc), X (execute), M (merge), S (strings), I (info),
      L (link order), O (extra OS processing required), G (group), T (TLS),
      C (compressed), x (unknown), o (OS specific), E (exclude),
      l (large), p (processor specific)
    """

    section_regex = re.compile(r'.*\] (?P<section>[^\s]*)\s*\w+\s*\w*\s*\w*\w*\s*(?P<size>\w*)')
    pic_regex = re.compile(r'\.rela?\.(data|text)')

    def __init__(self, path):
        self.path = path
        self.elf_files = []
        self.parsing_failed = False
        self.pic = False
        self.parse()

    def parse(self):
        r = subprocess.run(['readelf', '-W', '-S', self.path], encoding='utf8',
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if r.returncode != 0:
            self.parsing_failed = True
            return

        lines = [l for l in r.stdout.split('\n')]

        needle = 'Section Headers:'

        # archive files can contain multiple files
        while len(lines) > 0:
            parsed_sections = []
            lines = list(dropwhile(lambda x: needle not in x, lines))

            # skip header and empty section
            lines = lines[3:]

            sections = list(takewhile(lambda x: 'Key to Flags:' not in x, lines))
            for s in sections:
                r = self.section_regex.search(s)
                section = ElfSection(r.group('section'), r.group('size'))
                parsed_sections.append(section)

                # detect a PIC section
                if self.pic_regex.search(section.name) is not None:
                    self.pic = True

            lines = lines[len(sections):]
            if len(parsed_sections) > 0:
                self.elf_files.append(parsed_sections)


class ElfProgramHeaderInfo:
    """
    Program Headers:
      Type           Offset   VirtAddr           PhysAddr           FileSiz  MemSiz   Flg Align
      PHDR           0x000040 0x0000000000400040 0x0000000000400040 0x000268 0x000268 R   0x8
      INTERP         0x0002a8 0x00000000004002a8 0x00000000004002a8 0x00001c 0x00001c R   0x1
          [Requesting program interpreter: /lib64/ld-linux-x86-64.so.2]
      LOAD           0x000000 0x0000000000400000 0x0000000000400000 0x000460 0x000460 R   0x1000
      LOAD           0x001000 0x0000000000401000 0x0000000000401000 0x0002ad 0x0002ad R E 0x1000
      LOAD           0x002000 0x0000000000402000 0x0000000000402000 0x0001d0 0x0001d0 R   0x1000
      LOAD           0x002e00 0x0000000000403e00 0x0000000000403e00 0x000230 0x000238 RW  0x1000
      DYNAMIC        0x002e10 0x0000000000403e10 0x0000000000403e10 0x0001e0 0x0001e0 RW  0x8
      NOTE           0x0002c4 0x00000000004002c4 0x00000000004002c4 0x000044 0x000044 R   0x4
      GNU_EH_FRAME   0x002004 0x0000000000402004 0x0000000000402004 0x000054 0x000054 R   0x4
      GNU_STACK      0x000000 0x0000000000000000 0x0000000000000000 0x000000 0x000000 RW  0x10
      GNU_RELRO      0x002e00 0x0000000000403e00 0x0000000000403e00 0x000200 0x000200 R   0x1
    """

    header_regex = re.compile('\\s+(?P<header>\\w+)(\\s+\\w+){5}\\s+(?P<flags>[RWE ]{3}).*')

    def __init__(self, path):
        self.path = path
        self.headers = []
        self.parsing_failed = False
        self.parse()

    def parse(self):
        r = subprocess.run(['readelf', '-W', '-l', self.path], encoding='utf8',
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if r.returncode != 0:
            self.parsing_failed = True
            return

        lines = [l for l in r.stdout.split('\n')]
        needle = 'Program Headers:'

        while len(lines) > 0:
            lines = list(dropwhile(lambda x: needle not in x, lines))

            # skip header
            lines = lines[2:]

            sections = list(takewhile(lambda x: x.strip() != '', lines))
            for s in sections:
                r = self.header_regex.search(s)
                if r is not None:
                    self.headers.append(ElfProgramHeader(r.group('header'), r.group('flags')))

            lines = lines[len(sections):]


class ElfDynamicSectionInfo:
    """
    0x0000000000000001 (NEEDED)             Shared library: [ld-linux-x86-64.so.2]
    0x000000000000000e (SONAME)             Library soname: [libc.so.6]
    0x000000000000000c (INIT)               0x26950
    0x0000000000000019 (INIT_ARRAY)         0x1ba330
    0x000000000000001b (INIT_ARRAYSZ)       16 (bytes)
    0x0000000000000004 (HASH)               0x328
    0x000000006ffffef5 (GNU_HASH)           0x37f8
    0x0000000000000005 (STRTAB)             0x151e0
    0x0000000000000006 (SYMTAB)             0x7488
    0x000000000000000a (STRSZ)              24691 (bytes)
    0x000000000000000b (SYMENT)             24 (bytes)
    0x0000000000000003 (PLTGOT)             0x1bcbd0
    0x0000000000000002 (PLTRELSZ)           1152 (bytes)
    0x0000000000000014 (PLTREL)             RELA
    0x0000000000000017 (JMPREL)             0x24538
    0x0000000000000007 (RELA)               0x1c948
    0x0000000000000008 (RELASZ)             31728 (bytes)
    0x0000000000000009 (RELAENT)            24 (bytes)
    0x000000006ffffffc (VERDEF)             0x1c4c8
    0x000000006ffffffd (VERDEFNUM)          31
    0x000000000000001e (FLAGS)              BIND_NOW STATIC_TLS
    0x000000006ffffffb (FLAGS_1)            Flags: NOW
    0x000000006ffffffe (VERNEED)            0x1c918
    0x000000006fffffff (VERNEEDNUM)         1
    0x000000006ffffff0 (VERSYM)             0x1b254
    0x000000006ffffff9 (RELACOUNT)          1232
    0x0000000000000000 (NULL)               0x0
    """

    section_regex = re.compile('\\s+\\w*\\s+\\((?P<key>\\w+)\\)\\s+(?P<value>.*)')

    def __init__(self, path):
        self.path = path
        self.sections = []
        self.parsing_failed = False
        self.parse()
        self.parse_meta()

    def parse(self):
        r = subprocess.run(['readelf', '-W', '-d', self.path], encoding='utf8',
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if r.returncode != 0:
            self.parsing_failed = True
            return

        lines = [l for l in r.stdout.strip().split('\n')]
        needle = 'Dynamic section at offset'

        lines = list(dropwhile(lambda x: needle not in x, lines))
        # skip header
        lines = lines[2:]
        for line in lines:
            r = self.section_regex.search(line)
            self.sections.append(ElfDynamicSection(r.group('key'), r.group('value')))

    def parse_meta(self):
        self.soname = None
        soname = self['SONAME']
        if len(soname) == 1:
            value = soname[0]
            token = 'Library soname: ['
            assert value.startswith(token)
            assert value.endswith(']')
            self.soname = value[len(token):-1]

    def __getitem__(self, key):
        return [x.value for x in self.sections if x.key == key]


class ElfSymbolTableInfo:
    """
     7: 0000000000000000     0 SECTION LOCAL  DEFAULT    7
     8: 0000000000000000     0 SECTION LOCAL  DEFAULT    8
     9: 0000000000000000     0 SECTION LOCAL  DEFAULT    6
    10: 0000000000000000    18 FUNC    GLOBAL DEFAULT    4 main
    11: 0000000000000000    11 FUNC    GLOBAL DEFAULT    5 foo
    """

    section_regex = re.compile('\\s+[0-9]+:\\s\\w+\\s+(\\w+)\\s+(?P<type>\\w+)\\s+(?P<bind>\\w+)\\s+(?P<visibility>\\w+)\\s+\\w+\\s+(?P<name>\\S+)')

    def __init__(self, path):
        self.path = path
        self.symbols = []
        self.parsing_failed = False
        self.parse()

    def parse(self):
        r = subprocess.run(['readelf', '-W', '-s', self.path], encoding='utf8',
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if r.returncode != 0:
            self.parsing_failed = True
            return

        lines = [l for l in r.stdout.strip().split('\n')]
        for line in lines:
            r = self.section_regex.search(line)
            if r:
                self.symbols.append(ElfSymbol(r.group('type'), r.group('bind'),
                                              r.group('visibility'), r.group('name')))

    def get_functions_for_regex(self, regex):
        return [sym for sym in self.symbols if sym.type == 'FUNC' and re.search(sym.name, regex)]


class ReadelfParser:
    """
    Class contains all information obtained by readelf command
    in a structured format.
    """

    so_regex = re.compile(r'/lib(64)?/[^/]+\.so(\.[0-9]+)*$')

    def __init__(self, pkgfile_path, path):
        self.is_archive = path.endswith('.a')
        self.is_shlib = self.so_regex.search(path)
        self.is_debug = path.endswith('.debug')

        self.section_info = ElfSectionInfo(pkgfile_path)
        self.program_header_info = ElfProgramHeaderInfo(pkgfile_path)
        self.dynamic_section_info = ElfDynamicSectionInfo(pkgfile_path)
        self.symbol_table_info = ElfSymbolTableInfo(pkgfile_path)

    def parsing_failed(self):
        return (self.section_info.parsing_failed or
                self.program_header_info.parsing_failed or
                self.dynamic_section_info.parsing_failed or
                self.symbol_table_info.parsing_failed)
