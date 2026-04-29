"""
Lambda: Manage Rekognition Collection
CRUD operations for the face recognition collection.

API Endpoints:
    POST   /api/collection       - Create collection
    POST   /api/collection/faces - Index a face (add person)
    DELETE /api/collection/faces - Delete a face
    GET    /api/collection/faces - List all faces
"""

import json
import os
import logging
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

rekognition_client = boto3.client("rekognition")
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

COLLECTION_ID = os.environ.get("REKOGNITION_COLLECTION_ID", "home-security-faces")
RAW_BUCKET = os.environ.get("RAW_BUCKET")
KNOWN_PERSONS_TABLE = os.environ.get("KNOWN_PERSONS_TABLE")


def lambda_handler(event, context):
    """Route requests based on HTTP method and path."""
    method = event.get("httpMethod", "GET")
    path = event.get("path", "")

    logger.info("Request: %s %s", method, path)

    try:
        if path == "/api/collection" and method == "POST":
            return _create_collection()

        elif path == "/api/collection/faces":
            if method == "POST":
                return _index_face(event)
            elif method == "DELETE":
                return _delete_face(event)
            elif method == "GET":
                return _list_faces()

        return _response(404, {"error": "Not found"})

    except Exception as e:
        logger.exception("Error: %s", e)
        return _response(500, {"error": "Internal server error"})


def _create_collection():
    """Create a new Rekognition collection."""
    try:
        response = rekognition_client.create_collection(
            CollectionId=COLLECTION_ID
        )
        logger.info(
            "Collection created: %s (ARN: %s)",
            COLLECTION_ID,
            response["CollectionArn"],
        )
        return _response(200, {
            "message": f"Collection '{COLLECTION_ID}' created",
            "collection_arn": response["CollectionArn"],
        })
    except rekognition_client.exceptions.ResourceAlreadyExistsException:
        return _response(200, {
            "message": f"Collection '{COLLECTION_ID}' already exists"
        })
    except ClientError as e:
        logger.error("Create collection error: %s", e)
        return _response(500, {"error": str(e)})


def _index_face(event):
    """
    Index a face into the collection (register a known person).
    
    Body: {
        "personId": "person-123",
        "personName": "Nguyen Van A",
        "s3Key": "path/to/face.jpg"  (optional, if image already in S3)
    }
    
    Or upload image as base64 in body.
    """
    body = json.loads(event.get("body", "{}"))
    person_id = body.get("personId")
    person_name = body.get("personName", "")
    s3_key = body.get("s3Key")

    if not person_id:
        return _response(400, {"error": "Missing personId"})

    try:
        if s3_key:
            # Index from S3
            response = rekognition_client.index_faces(
                CollectionId=COLLECTION_ID,
                Image={
                    "S3Object": {
                        "Bucket": RAW_BUCKET,
                        "Name": s3_key,
                    }
                },
                ExternalImageId=person_id,
                MaxFaces=1,
                QualityFilter="AUTO",
                DetectionAttributes=["ALL"],
            )
        else:
            return _response(400, {"error": "Missing s3Key"})

        indexed_faces = response.get("FaceRecords", [])
        if not indexed_faces:
            return _response(400, {
                "error": "No face detected in the provided image"
            })

        face_id = indexed_faces[0]["Face"]["FaceId"]

        # Save person info to DynamoDB
        if KNOWN_PERSONS_TABLE:
            table = dynamodb.Table(KNOWN_PERSONS_TABLE)
            table.put_item(Item={
                "personId": person_id,
                "personName": person_name,
                "faceId": face_id,
                "s3Key": s3_key or "",
                "createdAt": datetime.now(timezone.utc).isoformat(),
            })

        logger.info(
            "Face indexed: person=%s, faceId=%s", person_id, face_id
        )
        return _response(200, {
            "message": f"Face indexed for '{person_id}'",
            "face_id": face_id,
            "person_id": person_id,
        })

    except ClientError as e:
        logger.error("Index face error: %s", e)
        return _response(500, {"error": str(e)})


def _delete_face(event):
    """
    Delete a face from the collection.
    Body: { "faceId": "xxx-xxx-xxx" }
    """
    body = json.loads(event.get("body", "{}"))
    face_id = body.get("faceId")

    if not face_id:
        return _response(400, {"error": "Missing faceId"})

    try:
        rekognition_client.delete_faces(
            CollectionId=COLLECTION_ID,
            FaceIds=[face_id],
        )
        logger.info("Face deleted: %s", face_id)
        return _response(200, {"message": f"Face '{face_id}' deleted"})
    except ClientError as e:
        logger.error("Delete face error: %s", e)
        return _response(500, {"error": str(e)})


def _list_faces():
    """List all faces in the collection."""
    try:
        faces = []
        response = rekognition_client.list_faces(
            CollectionId=COLLECTION_ID, MaxResults=100
        )
        faces.extend(response.get("Faces", []))

        # Paginate
        while "NextToken" in response:
            response = rekognition_client.list_faces(
                CollectionId=COLLECTION_ID,
                MaxResults=100,
                NextToken=response["NextToken"],
            )
            faces.extend(response.get("Faces", []))

        face_list = [
            {
                "face_id": f["FaceId"],
                "external_image_id": f.get("ExternalImageId", ""),
                "confidence": f.get("Confidence", 0),
            }
            for f in faces
        ]

        logger.info("Listed %d faces in collection '%s'", len(face_list), COLLECTION_ID)
        return _response(200, {
            "collection_id": COLLECTION_ID,
            "face_count": len(face_list),
            "faces": face_list,
        })
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            return _response(404, {
                "error": f"Collection '{COLLECTION_ID}' not found. Create it first."
            })
        logger.error("List faces error: %s", e)
        return _response(500, {"error": str(e)})


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }
