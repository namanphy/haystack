import numpy as np
import pytest
from elasticsearch import Elasticsearch

from haystack.database.base import Document, Label
from haystack.database.elasticsearch import ElasticsearchDocumentStore
from haystack.database.faiss import FAISSDocumentStore


def test_get_all_documents_without_filters(document_store_with_docs):
    documents = document_store_with_docs.get_all_documents()
    assert all(isinstance(d, Document) for d in documents)
    assert len(documents) == 3
    assert {d.meta["name"] for d in documents} == {"filename1", "filename2", "filename3"}
    assert {d.meta["meta_field"] for d in documents} == {"test1", "test2", "test3"}


def test_get_all_documents_with_correct_filters(document_store_with_docs):
    documents = document_store_with_docs.get_all_documents(filters={"meta_field": ["test2"]})
    assert len(documents) == 1
    assert documents[0].meta["name"] == "filename2"

    documents = document_store_with_docs.get_all_documents(filters={"meta_field": ["test1", "test3"]})
    assert len(documents) == 2
    assert {d.meta["name"] for d in documents} == {"filename1", "filename3"}
    assert {d.meta["meta_field"] for d in documents} == {"test1", "test3"}


def test_get_all_documents_with_incorrect_filter_name(document_store_with_docs):
    documents = document_store_with_docs.get_all_documents(filters={"incorrect_meta_field": ["test2"]})
    assert len(documents) == 0


def test_get_all_documents_with_incorrect_filter_value(document_store_with_docs):
    documents = document_store_with_docs.get_all_documents(filters={"meta_field": ["incorrect_value"]})
    assert len(documents) == 0


def test_get_documents_by_id(document_store_with_docs):
    documents = document_store_with_docs.get_all_documents()
    doc = document_store_with_docs.get_document_by_id(documents[0].id)
    assert doc.id == documents[0].id
    assert doc.text == documents[0].text


def test_write_document_meta(document_store):
    documents = [
        {"text": "dict_without_meta", "id": "1"},
        {"text": "dict_with_meta", "meta_field": "test2", "name": "filename2", "id": "2"},
        Document(text="document_object_without_meta", id="3"),
        Document(text="document_object_with_meta", meta={"meta_field": "test4", "name": "filename3"}, id="4"),
    ]
    document_store.write_documents(documents)
    documents_in_store = document_store.get_all_documents()
    assert len(documents_in_store) == 4

    assert not document_store.get_document_by_id("1").meta
    assert document_store.get_document_by_id("2").meta["meta_field"] == "test2"
    assert not document_store.get_document_by_id("3").meta
    assert document_store.get_document_by_id("4").meta["meta_field"] == "test4"


def test_write_document_index(document_store):
    documents = [
        {"text": "text1", "id": "1"},
        {"text": "text2", "id": "2"},
    ]
    document_store.write_documents([documents[0]], index="haystack_test_1")
    assert len(document_store.get_all_documents(index="haystack_test_1")) == 1

    if not isinstance(document_store, FAISSDocumentStore):  # addition of more documents is not supported in FAISS
        document_store.write_documents([documents[1]], index="haystack_test_2")
        assert len(document_store.get_all_documents(index="haystack_test_2")) == 1

    assert len(document_store.get_all_documents(index="haystack_test_1")) == 1
    assert len(document_store.get_all_documents()) == 0


def test_labels(document_store):
    label = Label(
        question="question",
        answer="answer",
        is_correct_answer=True,
        is_correct_document=True,
        document_id="123",
        offset_start_in_doc=12,
        no_answer=False,
        origin="gold_label",
    )
    document_store.write_labels([label], index="haystack_test_label")
    labels = document_store.get_all_labels(index="haystack_test_label")
    assert len(labels) == 1

    labels = document_store.get_all_labels()
    assert len(labels) == 0


@pytest.mark.parametrize("document_store_with_docs", ["elasticsearch"], indirect=True)
def test_elasticsearch_update_meta(document_store_with_docs):
    document = document_store_with_docs.query(query=None, filters={"name": ["filename1"]})[0]
    document_store_with_docs.update_document_meta(document.id, meta={"meta_field": "updated_meta"})
    updated_document = document_store_with_docs.query(query=None, filters={"name": ["filename1"]})[0]
    assert updated_document.meta["meta_field"] == "updated_meta"


def test_elasticsearch_custom_fields(elasticsearch_fixture):
    client = Elasticsearch()
    client.indices.delete(index='haystack_test_custom', ignore=[404])
    document_store = ElasticsearchDocumentStore(index="haystack_test_custom", text_field="custom_text_field",
                                                embedding_field="custom_embedding_field")

    doc_to_write = {"custom_text_field": "test", "custom_embedding_field": np.random.rand(768).astype(np.float32)}
    document_store.write_documents([doc_to_write])
    documents = document_store.get_all_documents()
    assert len(documents) == 1
    assert documents[0].text == "test"
    np.testing.assert_array_equal(doc_to_write["custom_embedding_field"], documents[0].embedding)
