#!/usr/bin/env python2

# NOTE:
# mistakenly started an inkscape script to automatically export assets to png,
# to the assets dir. doesn't seem necessary because inkscape seems to remember
# the directory and use the object id for the name.

import argparse
import os
import shutil
import sys
import subprocess

p = subprocess.Popen(['inkscape', '-x'], stdout=subprocess.PIPE)
extensionpath, stderr = p.communicate()
sys.path.append(extensionpath.strip())
del p, extensionpath, stderr

import inkex
from simplestyle import *

class HelloWorldEffect(inkex.Effect):
    """
    Example Inkscape effect extension.
    Creates a new layer with a "Hello World!" text centered in the middle of
    the document.
    """
    def __init__(self):
        """
        Constructor.
        Defines the "--what" option of a script.
        """
        inkex.Effect.__init__(self)

        # Define string option "--what" with "-w" shortcut and default value "World".
        self.OptionParser.add_option('-w', '--what', action = 'store',
          type = 'string', dest = 'what', default = 'World',
          help = 'What would you like to HELLO greet?')

    def _affect(self, args=sys.argv[1:], output=True):
        # TODO: left off here. have to jump in front of inkex's command line processing.
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        subparser = subparsers.add_parser('install')
        subparser.set_defaults(func=install)
        args = parser.parse_args()
        print('Hello')
        args.func()

    def effect(self):
        """
        Effect behaviour.
        Overrides base class' method and inserts "Hello World" text into SVG document.
        """
        # Get script's "--what" option value.
        what = self.options.what

        # Get access to main SVG document element and get its dimensions.
        svg = self.document.getroot()
        # or alternatively
        # svg = self.document.xpath('//svg:svg',namespaces=inkex.NSS)[0]

        # Again, there are two ways to get the attibutes:
        width  = self.unittouu(svg.get('width'))
        height = self.unittouu(svg.attrib['height'])

        # Create a new layer.
        layer = inkex.etree.SubElement(svg, 'g')
        layer.set(inkex.addNS('label', 'inkscape'), 'Hello %s Layer' % (what))
        layer.set(inkex.addNS('groupmode', 'inkscape'), 'layer')

        # Create text element
        text = inkex.etree.Element(inkex.addNS('text','svg'))
        text.text = 'Hello %s!' % (what)

        # Set text position to center of document.
        text.set('x', str(width / 2))
        text.set('y', str(height / 2))

        # Center text horizontally with CSS style.
        style = {'text-align' : 'center', 'text-anchor': 'middle'}
        text.set('style', formatStyle(style))

        # Connect elements together.
        layer.append(text)


def install():
    userextdir = os.path.expanduser('~/.config/inkscape/extensions/')
    shutil.copy2(__file__, userextdir)
    # TODO: autogenerate the inx file.
    filename, _ = os.path.splitext(os.path.basename(__file__))
    shutil.copy2(filename + '.inx', userextdir)

def main():
    """
    """
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    subparser = subparsers.add_parser('install')
    subparser.set_defaults(func=install)
    args = parser.parse_args()


effect = HelloWorldEffect()
effect.affect()
