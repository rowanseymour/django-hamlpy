import re

from elements import Element

ELEMENT = '%'
ID = '#'
CLASS = '.'

HTML_COMMENT = '/'
HAML_COMMENT = '-#'

VARIABLE = '='
TAG = '-'

JAVASCRIPT_FILTER = ':javascript'
CSS_FILTER = ':css'
PLAIN_FILTER = ':plain'

ELEMENT_CHARACTERS = (ELEMENT, ID, CLASS)

def create_node(haml_line):
    stripped_line = haml_line.strip()
    
    if not stripped_line:
        return None
    
    if stripped_line[0] in ELEMENT_CHARACTERS:
        return ElementNode(haml_line)
    
    if stripped_line[0] == HTML_COMMENT:
        return CommentNode(haml_line)
    
    if stripped_line.startswith(HAML_COMMENT):
        return HamlCommentNode(haml_line)
    
    if stripped_line[0] == VARIABLE:
        return VariableNode(haml_line)
    
    if stripped_line[0] == TAG:
        return TagNode(haml_line)
    
    if stripped_line == JAVASCRIPT_FILTER:
        return JavascriptFilterNode(haml_line)
    
    if stripped_line == CSS_FILTER:
        return CssFilterNode(haml_line)
    
    if stripped_line == PLAIN_FILTER:
        return PlainFilterNode(haml_line)
    
    return HamlNode(haml_line)

class RootNode:
    
    def __init__(self):
        self.indentation = -1
        self.internal_nodes = []
    
    def add_node(self, node):
        if (node == None):
            return
        
        if (self._should_go_inside_last_node(node)):
            self.internal_nodes[-1].add_node(node)
        else:
            self.internal_nodes.append(node)
    
    def _should_go_inside_last_node(self, node):
        return self.internal_nodes and (node.indentation > self.internal_nodes[-1].indentation or self.internal_nodes[-1].should_contain(node))
    
    def render(self):
        return self.render_internal_nodes()
    
    def render_internal_nodes(self):
        result = ''
        for node in self.internal_nodes:
            result += ('%s\n') % node.render()
        return result
    
    def has_internal_nodes(self):
        return len(self.internal_nodes) > 0
    
    def should_contain(self, node):
        return False
      
        
class HamlNode(RootNode):
    
    def __init__(self, haml):
        RootNode.__init__(self)
        self.haml = haml.strip()
        self.raw_haml = haml
        self.indentation = (len(haml) - len(haml.lstrip()))
        self.spaces = ''.join(' ' for i in range(self.indentation))
        
    
    def render(self):
        return "".join([self.spaces, self.haml, '\n', self.render_internal_nodes()])


class ElementNode(HamlNode):
    
    def __init__(self, haml):
        HamlNode.__init__(self, haml)
        self.django_variable = False
    
    def render(self):
        return self._render_tag()
    
    def _render_tag(self):
        element = Element(self.haml)
        self.django_variable = element.django_variable
        return self._generate_html(element)
        
    def _generate_html(self, element):        
        if self.indentation > 0:
            result = "%s<%s" % (self.spaces, element.tag) 
        else:
            result = "<%s" % element.tag 

        if element.id:
            result += " id='%s'" % element.id 
        if element.classes:
            result += " class='%s'" % element.classes 
        if element.attributes:
            result += ' ' + element.attributes            
            
        content = self._render_tag_content(element.inline_content)
        
        if element.self_close and not content:
            result += " />"
        else:
            result += ">%s</%s>" % (content, element.tag)
        
        return result
    
    def _render_tag_content(self, current_tag_content):
        if self.has_internal_nodes():
            current_tag_content = '\n' + self.render_internal_nodes() + self.spaces
        if current_tag_content == None:
            current_tag_content = ''
        if self.django_variable:
            current_tag_content = "{{ " + current_tag_content.strip() + " }}"
        current_tag_content = re.sub(r'#\{([a-zA-Z0-9\.\_]+)\}', r'{{ \1 }}', current_tag_content)
        return current_tag_content


class CommentNode(HamlNode):
    
    def __init__(self, haml):
        HamlNode.__init__(self, haml)
        self.haml = haml.strip().lstrip(HTML_COMMENT).strip()
    
    def render(self):
        content = ''
        if self.has_internal_nodes():
            content = '\n' + self.render_internal_nodes()
        else:
            content = self.haml + ' '
        
        return "<!-- %s-->" % content


class HamlCommentNode(HamlNode):
    def __init__(self, haml):
        HamlNode.__init__(self, haml)
    
    def render(self):
        return ''


class VariableNode(ElementNode):
    def __init__(self, haml):
        ElementNode.__init__(self, haml)
        self.django_variable = True
    
    def render(self):
        tag_content = self.haml.lstrip(VARIABLE)
        return "%s%s" % (self.spaces, self._render_tag_content(tag_content))


class TagNode(HamlNode):
    self_closing = {'for':'endfor',
                    'if':'endif',
                    'block':'endblock',
                    'filter':'endfilter',
                    'autoescape':'endautoescape',
                    }
    may_contain = {'if':'else', 'for':'empty'}
    
    def __init__(self, haml):
        HamlNode.__init__(self, haml)
        self.tag_statement = self.haml.lstrip(TAG).strip()
        self.tag_name = self.tag_statement.split(' ')[0]
        
        if (self.tag_name in self.self_closing.values()):
            raise TypeError("Do not close your Django tags manually.  It will be done for you.")
    
    def render(self):
        internal = self.render_internal_nodes()
        output = "%s{%% %s %%}\n%s" % (self.spaces, self.tag_statement, internal)
        if (self.tag_name in self.self_closing.keys()):
            output += '%s{%% %s %%}' % (self.spaces, self.self_closing[self.tag_name])
        return output
    
    def should_contain(self, node):
        return isinstance(node,TagNode) and self.may_contain.get(self.tag_name,'') == node.tag_name


class FilterNode(HamlNode):
  def add_node(self, node):
      if (node == None):
          return
      else:
          self.internal_nodes.append(node)


class PlainFilterNode(FilterNode):
    def render(self):
        return "".join([node.raw_haml + '\n' for node in self.internal_nodes])


class JavascriptFilterNode(FilterNode):
    def render(self):
        output = '<script type=\'text/javascript\'>\n// <![CDATA[\n'
        output += "".join([node.raw_haml for node in self.internal_nodes])
        output += '// ]]>\n</script>'
        return output
        
        
class CssFilterNode(FilterNode):
    def render(self):
        output = '<style type=\'text/css\'>\n/*<![CDATA[*/\n'
        output += "".join([node.raw_haml for node in self.internal_nodes])
        output += '/*]]>*/\n</style>'
        return output
        