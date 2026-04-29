"""
Rekognition Service
Wraps Amazon Rekognition API calls for face detection and recognition.
"""

import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()

rekognition_client = boto3.client("rekognition")


def detect_faces(image_bytes: bytes) -> list[dict]:
    """
    Detect faces in an image.

    Args:
        image_bytes: Raw image bytes (JPEG/PNG).

    Returns:
        List of face details from Rekognition.
    """
    try:
        response = rekognition_client.detect_faces(
            Image={"Bytes": image_bytes},
            Attributes=["ALL"],
        )
        faces = response.get("FaceDetails", [])
        logger.info("DetectFaces: found %d face(s)", len(faces))
        return faces
    except ClientError as e:
        logger.error("Rekognition DetectFaces error: %s", e)
        return []


def search_faces_by_image(
    image_bytes: bytes,
    collection_id: str,
    max_faces: int = 5,
    threshold: float = 80.0,
) -> list[dict]:
    """
    Search for matching faces in a Rekognition collection.

    Args:
        image_bytes: Raw image bytes.
        collection_id: Rekognition collection ID.
        max_faces: Max faces to return.
        threshold: Minimum confidence threshold.

    Returns:
        List of matched faces with person info.
    """
    try:
        response = rekognition_client.search_faces_by_image(
            CollectionId=collection_id,
            Image={"Bytes": image_bytes},
            MaxFaces=max_faces,
            FaceMatchThreshold=threshold,
        )

        matches = []
        for match in response.get("FaceMatches", []):
            face_info = {
                "face_id": match["Face"]["FaceId"],
                "external_image_id": match["Face"].get("ExternalImageId", ""),
                "similarity": match["Similarity"],
                "confidence": match["Face"].get("Confidence", 0),
            }
            matches.append(face_info)

        logger.info(
            "SearchFacesByImage: %d match(es) in collection '%s'",
            len(matches),
            collection_id,
        )
        return matches

    except rekognition_client.exceptions.InvalidParameterException:
        logger.info("No face detected in image for search")
        return []
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            logger.warning("Collection '%s' not found", collection_id)
        else:
            logger.error("Rekognition SearchFacesByImage error: %s", e)
        return []


def get_face_match_result(
    image_bytes: bytes, collection_id: str, threshold: float = 80.0
) -> dict:
    """
    High-level function: detect faces and search for matches.
    
    Returns:
        {
            "face_count": int,
            "faces_detected": [...],
            "matches": [...],
            "status": "known" | "unknown" | "no_face",
            "best_match": {...} | None
        }
    """
    # Detect faces
    faces = detect_faces(image_bytes)
    if not faces:
        return {
            "face_count": 0,
            "faces_detected": [],
            "matches": [],
            "status": "no_face",
            "best_match": None,
        }

    # Search for matches in collection
    matches = search_faces_by_image(
        image_bytes, collection_id, threshold=threshold
    )

    best_match = None
    status = "unknown"

    if matches:
        best_match = max(matches, key=lambda m: m["similarity"])
        status = "known"
        logger.info(
            "Best match: person=%s, similarity=%.1f%%",
            best_match["external_image_id"],
            best_match["similarity"],
        )

    return {
        "face_count": len(faces),
        "faces_detected": faces,
        "matches": matches,
        "status": status,
        "best_match": best_match,
    }
