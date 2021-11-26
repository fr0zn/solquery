from solquery_compare import compare_levels
from tree_sitter import Language, Parser
from anytree import RenderTree, NodeMixin,PreOrderIter,LevelOrderGroupIter
from anytree.exporter import DotExporter,UniqueDotExporter
import yaml
import re

def sexp_format(sexp):
    _str = ''
    _indent = -1
    _inspace = False
    _inbraket = False
    for c in sexp:
        if c == '(':
            _indent += 1
            _inspace = False
            _inbraket = True
        elif c == ')':
            if not _inbraket:
                _str += ' '*_indent
            _str += ')\n'
            _indent -= 1
            _inbraket = False
            continue
        elif c == ' ':
            if not _inspace:
                if _inbraket:
                    _str += '\n'
                _str += ' '*_indent
                _inspace = True
        _str += c

    return _str

class TreeNode(NodeMixin):
    def __init__(self, type, node, content, parent=None, children=None):
        super(TreeNode, self).__init__()
        self.name = "{}".format(type)
        self.type = type
        self.node = node
        self.parent = parent
        self.is_named = node.is_named if node else False
        self.is_ellipsis = False
        self.is_comma = False
        self.is_comment = False
        self.content = content
        if children:
            self.children = children


    # def getcontent(self, start=0, end=-1):
    #     if end == -1:
    #         end = len(self.__content)
    #     return self.__content[start:end].decode("utf-8")

    # content=property(getcontent)

    def __repr__(self):
        return self.__str__()

    def sexp(self):
        return self.type


    def __str__(self):
        # return str(self.node)
        # if len(self.children) == 0:
        #     return "{} - '{}'".format(self.content, self.name)
        # else:
        return "'{}'".format(self.name)

class TreeRoot():
    def __init__(self, _content, _root):

        self.root = None

        self._root = _root
        self._src = _content

        self._sexp = ''
        self.rules = []

        # self.metavars = {}

        self._prepare_traverse()

    def get_sexp(self, filters=[]):
        _sexp = ''
        def _traverse_sexp(node):
            nonlocal _sexp
            if node.type not in filters and node.is_named:
                _sexp += '('
                _sexp += "{} ".format(node.type)
                for child in node.children:
                    _traverse_sexp(child)
                _sexp += ')'
        _traverse_sexp(self.root)
        return _sexp

    def filter_type(self, filterTypes):
        sexp = self.get_sexp(filters=filterTypes)
        return sexp

    def _parse_node(self, _node, _last_parent):
        node = TreeNode(_node.type, _node, self._src[_node.start_byte:_node.end_byte], parent=_last_parent)
        if _node.type == 'ellipsis':
            node.is_ellipsis = True
        elif _node.type == ',':
            node.is_comma = True
        elif _node.type == 'comment':
            node.is_comment = True

        if self.root == None:
            self.root = node
        # if node.type == 'identifier':
        #     _identifier = node.content
        #     if _identifier.startswith('$'):
        #         node.is_meta = True
        #         if _identifier not in self.metavars:
        #             self.metavars[_identifier] = None #MetaVar(node)
        return node

    def _prepare_traverse(self):
        last_parent = None
        def _traverse(node, last_parent):
            last_parent = self._parse_node(node, last_parent)
            for child in node.children:
                _traverse(child, last_parent)
        _traverse(self._root, last_parent)

    def __str__(self):
        return str(RenderTree(self.root))

    def dot(self):
        UniqueDotExporter(self.root).to_picture("TreeRoot.png")

    # def __repr__(self) -> str:
    #     return self.__str__()

# class MetaVar():
#     def __init__(self, node):
#         self.node = node
#         self.value = None

#     def __repr__(self):
#         return "{}({})".format(self.node.content, self.value)


class QueryStates():
    def __init__(self):
        self.meta_vars = {}
        self.is_match = False
        self._matched_nodes = []
        self._is_skip = False
        self._added_meta = []

    def get_range(self):
        if len(self._matched_nodes) > 0:
            return (self._matched_nodes[0].node.start_byte, self._matched_nodes[-1].node.end_byte)
        else:
            return (0, -1)

    def __repr__(self) -> str:
        return '{} - {}'.format(self.is_match, self.meta_vars)

class SolidityQuery():

    def __init__(self):
        self._build_load_library()
        self.parser = Parser()
        self.parser.set_language(self.SOLIDITY_LANGUAGE)

        self.src = None
        self.queries = None

        self.current_state = None

        # list of QueryStates()
        self.query_states = []

    def _build_load_library(self):
        Language.build_library('build/solidity.so',[ '.' ])
        self.SOLIDITY_LANGUAGE = Language('build/solidity.so', 'solidity')

    def _parse_file(self, fileName):
        _content = bytes(open(fileName).read().strip(), 'utf8')
        # Append and prepend ellipsis to the query
        # _content = '...\n' + _content + '\n...'
        # _content = _content + '\n...'
        return (_content, self.parser.parse(_content))

    def load_source_string(self, string):
        _content = bytes(string.strip(), 'utf8')
        _tree = self.parser.parse(_content)
        self.src = TreeRoot(_content, _tree.root_node)
        return self.src

    def load_query_string(self, string):
        _content = bytes(string.strip(), 'utf8')
        _tree = self.parser.parse(_content)
        self.queries = TreeRoot(_content, _tree.root_node)
        return self.queries

    def load_source_file(self, fileName):
        _content, _tree = self._parse_file(fileName)
        # TODO: Checks MISSING ERROR
        self.src = TreeRoot(_content, _tree.root_node)
        return self.src

    def load_query_yaml(self, fileName):
        with open(fileName, "r") as stream:
            try:
                _data = yaml.safe_load(stream)
                # TODO: Validate yaml
                self.rules = _data['rules']
                # TODO: Multiple rules
                # TODO: Check for pattern-not/or etc etc
                _content = self.rules[0]['pattern']
                _tree = self.parser.parse(bytes(_content, 'utf8'))
                self.queries = TreeRoot(_content, _tree.root_node)
            except yaml.YAMLError as exc:
                print(exc)
        # TODO: Checks MISSING ERROR
        return self.queries


    def load_query_file(self, fileName):
        _content, _tree = self._parse_file(fileName)
        # TODO: Checks MISSING ERROR
        self.queries = TreeRoot(_content, _tree.root_node)
        return self.queries

    def _is_skip(self):
        return self.current_state._is_skip

    def _after_skip(self):
        for added in self.current_state._added_meta:
            self.current_state.meta_vars.pop(added)
        self.current_state._added_meta = []

    def _is_match(self, node):
        self.current_state._matched_nodes.append(node)
        self.current_state._added_meta = []

    def _add_meta_compare(self, _metavar, _content):
        # _metavar = searchNode.content
        # _content = compareNode.content
        if _metavar not in self.current_state.meta_vars:
            self.current_state._added_meta.append(_metavar)
            self.current_state.meta_vars[_metavar] = _content
            return True
        else:
            # The node is equal if the metavar is the same
            return self.current_state.meta_vars[_metavar] == _content


    ######################################

    def _compare_identifier(self, searchNode, compareNode, args):
        _starts = args['starts']
        _skip = args.get('skip', False)
        if _skip:
            self.current_state._is_skip = True
        if searchNode.content.startswith(_starts):
            return self._add_meta_compare(
                searchNode.content,
                compareNode.content
            )
        # True if both identifiers are the same
        return searchNode.content == compareNode.content

    def _compare_strings(self, searchNode, compareNode, args):
        # Removes ' and "
        _merged_compare = ''.join([c.content[1:-1].decode('utf8') for c in compareNode.children if c.type != 'comment'])
        _merged_search = ''.join([c.content[1:-1].decode('utf8') for c in searchNode.children if c.type != 'comment'])
        self.current_state._is_skip = True
        if _merged_search.startswith('$STRING'):
           return self._add_meta_compare(
                _merged_search,
                _merged_compare
            )
        return bool(re.search(_merged_search, _merged_compare))


    def _compare_default(self, searchNode, compareNode, args):
        if searchNode.type == compareNode.type:
            print('TRUE', searchNode.type, compareNode.type)
            return True
        else:
            print('DIFF', searchNode.type, compareNode.type)
            return False

    # Search node -> Compare Node -> (handler, data)

    def _compareNodes(self, searchNode, compareNode):
        SOLIDITY_NODES = {
            # ('ellipsis', 'ellipsis'): (lambda x: True, None),
            # ('contract_declaration', 'contract_declaration'): (lambda x: True, None),
            # ('contract_body', 'contract_body'): (lambda x: True, None),
            # ('state_variable_declaration', 'state_variable_declaration'): (lambda x: True, None),
            ('identifier', 'identifier')                          : (self._compare_identifier, {'starts':b'$'}),
            ('identifier', 'number_literal')                      : (self._compare_identifier, {'starts':b'$'}),
            ('primitive_type', 'primitive_type')                  : (self._compare_identifier, {'starts':b'$TYPE', 'skip':True}),
            ('visibility', 'visibility')                          : (self._compare_identifier, {'starts':b'$VISIBILITY'}),
            ('state_mutability', 'state_mutability')              : (self._compare_identifier, {'starts':b'$STATE'}),
            ('storage_location', 'storage_location')              : (self._compare_identifier, {'starts':b'$STORAGE'}),
            ('pragma_versions', 'pragma_versions')                : (self._compare_identifier, {'starts':b'$VERSION', 'skip':True}),
            ('experimental_directives', 'experimental_directives'): (self._compare_identifier, {'starts':b'$EXPERIMENTAL'}),
            ('string_literal', 'string_literal')                  : (self._compare_strings, {}),
        }
        self.current_state._is_skip = False

        _fnc, _data = SOLIDITY_NODES.get(
            (searchNode.type, compareNode.type),
            (self._compare_default, {})
            )

        return _fnc(searchNode, compareNode, _data)

    def _do_query(self):
        # ellipsis_node = TreeNode('ellipsis', None, '...')
        # commaNode = TreeNode(',', None, ',')
        # We are getting the firs rule of the query as an start point
        # If we find any we will get the parent, and pre/appended ellipsis
        # during query load will do the rest
        query_first_rule = None
        # Skip until the find the first rule of the query that is not an ellipsis
        for child in self.queries.root.children:
            if not child.is_ellipsis:
            # if not self._compareNodes(child, ellipsis_node):
                query_first_rule = child
                break

        _single_statement = False
        for src_node in PreOrderIter(self.src.root):
            self.current_state = QueryStates()
            print('============= CHECKING NODES ================')
            # print(src_node)
            # print(query_first_rule)
            # print('===========')
            # if src_node.type == query_first_rule.type:
            if self._compareNodes(query_first_rule, src_node):
                # This is done because we want to support multistatment
                # with ellipsis. So we betch a common root branch that contains
                # the first found rule and allows ellipis skipping
                if _single_statement:
                    _src_parent = src_node
                    _query_parent = self.queries.root.children[0]
                    _srcIndexStart = 0
                else:
                    _src_parent = src_node.parent
                    _query_parent = self.queries.root
                    _srcIndexStart = _src_parent.children.index(src_node)
                print('=========== SRC TREE ============')
                print(str(RenderTree(_src_parent)))
                print('=========== SRC CONTENT ============')
                print(src_node.content)
                print()
                print('=========== QUERY TREE ============')
                print(self.queries)
                print('=========== QUERY CONTENT ============')
                print(self.queries.root.content)
                # We are queriying using the full queries root content
                # We use the parent of the found src node for the first query
                # rule but skipped n times, where n is the index of the found
                # child
                _match = compare_levels(_src_parent, _query_parent,
                        # ellipsisNode=ellipsis_node,
                        # commaNode=commaNode,
                        compareFunction=self._compareNodes,
                        srcIndexStart=_srcIndexStart,
                        isSkipFunction=self._is_skip,
                        afterSkipFunction=self._after_skip,
                        isMatchFunction=self._is_match,
                        # data=self.query_data[self.query_index]
                        # metaVars=self.query_metavars[self.query_index],
                        )
                self.current_state.is_match = _match
                self.query_states.append(self.current_state)

                print('=========== MATCH ============')
                print(_match)
                print(self.query_states)
                print('==============================')
                # break

        print()
        print('================= RESULTS ==================')
        for query_result in self.query_states:
            if query_result.is_match:
                _start, _end = query_result.get_range()
                print('''============================
Content {} - {}:

{}

Metavars:
{}'''.format(_start, _end, self.src.root.content[_start:_end].decode('utf8'), query_result.meta_vars))
                # print(_start, _end)
                # print('-------------')
                # print(self.src.root.content[_start:_end])
                # print('-------------')
                # print(query_result.meta_vars)

        # print([x.is_match for x in self.query_states])
        # print([x._matched_nodes for x in self.query_states])
        print('=============')
        return self.query_states

    def query(self):
        # for i,query in enumerate(self.queries):
        return self._do_query()

        print(sexp_format(query_sexp))
        captures = query.captures(self.src_treecontent.root)
        self._parse_captures_with_meta(captures)
        return captures

sq = SolidityQuery()
t = sq.load_source_file('test.sol')
# qs = sq.load_query_yaml('query.yaml')
qs = sq.load_query_file('query.sol')

# t.dot()

# print(t)
# for q in qs:
#     print(q)
#     print(q.get_sexp())
#     print(q.metavars)

print(sq.query())


# sq.format_query()