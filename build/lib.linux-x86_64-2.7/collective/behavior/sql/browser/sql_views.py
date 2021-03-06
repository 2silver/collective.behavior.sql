import logging
from zope import component, interface, schema
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from collective.saconnect.interfaces import ISQLAlchemyConnectionStrings
from Products.CMFCore.interfaces import ISiteRoot
from Products.Five.browser import BrowserView
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import scoped_session, sessionmaker, relation
from zope.sqlalchemy import ZopeTransactionExtension
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from plone.directives import form
from zope import schema
from z3c.form import button, field
from collective.behavior.sql import _

LOG = logging.getLogger(__name__)

class ITestForm(form.Schema):
    """ Define form fields """

    connection = schema.Choice(
        title=_(u"label_connection", default=u"Connection"),
        vocabulary=SimpleVocabulary([])
        )

    table = schema.Choice(
        title=_(u"label_table", default=u"Table"),
        required=False,
        values=[u'a',u'b',u'c']
        )

    columns = schema.List(
        title=_(u"label_columns", default=u"Columns"),
        required=False,
        value_type=schema.Choice(values=[])
        )

class TestView(form.Form):
    ignoreContext = True
    template = ViewPageTemplateFile('templates/sql_test.pt')

    def __init__(self, context, request):
        super(TestView, self).__init__(context, request)
        self.saconnect = ISQLAlchemyConnectionStrings(
            component.getUtility(ISiteRoot))
        self.Base = None
        self.tablesVoc = []
        self.table = []
        self.columnsVoc = []
        self.columns = []
        self.items = []

    def updateFields(self):
        fields = field.Fields(ITestForm)
        connections = []
        for name, url in self.saconnect.items():
            connections.append(SimpleTerm(url, url, name))
        fields['connection'].field.vocabulary = SimpleVocabulary(connections)
        if len(connections) == 1:
            if self.Base == None:
               self.initBase(connections[0].value)
            self.tablesVoc = self.getTables()
            fields['table'].field.vocabulary = SimpleVocabulary.fromValues(self.tablesVoc)
            if len(self.tablesVoc) == 1:
                self.columnsVoc = self.getColumns(self.tablesVoc[0])
                fields['columns'].field.value_type.vocabulary = SimpleVocabulary.fromValues(self.columnsVoc)
                fields['columns'].field.default = fields['columns'].field.values
        self.fields = fields
    
    def update(self):
        self.updateFields()
        self.updateWidgets()
        data, errors = self.extractData()
        table = data.get('table')
        if data.get('connection'):
            if self.Base == None:
                self.initBase(data.get('connection'))
            if not self.tablesVoc:
                self.tablesVoc = self.getTables()
            self.fields['table'].field.vocabulary = SimpleVocabulary.fromValues(self.tablesVoc)
            if len(self.tablesVoc) == 1 and table == None:
                table = self.tablesVoc[0]
        if table:
            if not self.columnsVoc:
                self.columnsVoc = self.getColumns(table)
            self.fields['columns'].field.value_type.vocabulary = SimpleVocabulary.fromValues(self.columnsVoc)
#            self.fields['columns'].field.value_type.default = self.columnsVoc
        super(TestView, self).update()
    
    def initBase(self, url):
        engine = create_engine(url, echo=True)
        self.Base = automap_base(bind=engine)
    
    def getTables(self):
        conn = self.Base.metadata.bind.connect()
        return self.Base.metadata.bind.engine.table_names([], connection=conn)
    
    def getColumns(self, table):
        self.Base.metadata.reflect(only=[table])
        return [a.name for a in self.Base.metadata.tables[table].c]

    def getItems(self, table, columns):
        self.Base.prepare(self.Base.metadata.bind)
        Session = scoped_session(sessionmaker(bind=self.Base.metadata.bind, extension=ZopeTransactionExtension()))
        session = Session()
        item = getattr(self.Base.classes, table, None)
        return session.query(item).all()

    @button.buttonAndHandler(_('Apply'), name='apply')
    def handleApply(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return
        if data.get('table') and data.get('columns'):
            self.table = data.get('table')
            self.columns = data.get('columns')
            self.items = self.getItems(self.table, self.columns)

