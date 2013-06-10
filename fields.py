from django.db.models import AutoField, SubfieldBase

from google.appengine.api.datastore import Key
from google.appengine.ext import db
from django.db.models.sql.where import Constraint

class AncestorNode(Constraint):
    def __init__(self, instance):
        self.instance = instance

class PossibleDescendent(object):
    @classmethod
    def descendents_of(cls, instance):
        qs = cls.objects.all()

        #Add our own custom constraint type to mark this as an ancestor query
        #this is used in GAEQuery._decode_child and then switched for a custom filter
        #which is passed to GAEQuery.add_filter where we set the ancestor_key
        qs.query.where.add(
            (Constraint(None, '__ancestor', instance._meta.pk), 'exact', instance),
            'AND'
        )
        return qs

    def parent(self):
        if isinstance(self._meta.pk, GAEKeyField):
            return self._meta.pk.ancestor_model.objects.get(pk=self._meta.pk._parent_key.id_or_name())
        return None

class AncestorKey(object):
    def __init__(self, ancestor, key_id=None):
        self.ancestor = ancestor
        self.key_id = key_id

class GAEKeyField(AutoField):
    #Make sure to_python is called on assignments
    __metaclass__ = SubfieldBase

    def __init__(self, ancestor_model, *args, **kwargs):
        self.ancestor_model = ancestor_model
        self._parent_key = None
        self._id = None

        kwargs["primary_key"] = True
        super(GAEKeyField, self).__init__(*args, **kwargs)

    def get_db_prep_value(self, value, connection, prepared=False):
        if self._parent_key:
            return Key.from_path(self.model._meta.db_table, value or self._id, parent=self._parent_key)

        return super(GAEKeyField, self).get_db_prep_value(value, connection, prepared)

    def to_python(self, value):
        #FIXME: throw exception if connection != datastore
        if value and isinstance(value, AncestorKey):
            if value.ancestor.__class__ != self.ancestor_model:
                raise ValueError("Tried to set ancestor of incorrect type")

            #Get the parent key
            self._parent_key = Key.from_path(
                self.ancestor_model._meta.db_table,
                value.ancestor.pk
            )

            #If no ID value was specified
            if not value.key_id:
                #Generate a key and store it on the field
                self._id = db.allocate_ids(
                    self._parent_key,
                    1
                )[0]
                return None
            else:
                self._id = value.key_id

            #Return the generated ID
            return value.key_id
        else:
            return super(GAEKeyField, self).to_python(value)

