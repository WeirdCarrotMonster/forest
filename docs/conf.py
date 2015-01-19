import sys
import os

sys.path.insert(0, os.path.abspath('..'))

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.doctest',
]

templates_path = ['_templates']

source_suffix = '.rst'

master_doc = 'index'

project = u'Forest PaaS'
copyright = u'2015, Eugene Protozanov'

version = '0.5'
release = '0.5'

exclude_patterns = ['_build']
pygments_style = 'sphinx'

html_theme = 'default'
html_static_path = ['_static']
htmlhelp_basename = 'ForestPaaSdoc'

latex_elements = {
}

latex_documents = [
    ('index', 'ForestPaaS.tex', u'Forest PaaS Documentation',
        u'Eugene Protozanov', 'manual'),
]

man_pages = [
    ('index', 'forestpaas', u'Forest PaaS Documentation',
     [u'Eugene Protozanov'], 1)
]
texinfo_documents = [
    ('index', 'ForestPaaS', u'Forest PaaS Documentation',
        u'Eugene Protozanov', 'ForestPaaS', 'One line description of project.',
        'Miscellaneous'),
]
