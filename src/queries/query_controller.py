import json
from flask import request, jsonify, send_from_directory
from src import app
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.queries.query_service import QueryService
from src.queries.dto.query_dto import QueryDTO
from src.queries.dto.execute_query_dto import ExecuteQueryDTO
from config import Queue, FileRepo
from src.nib_user.nib_user_repo import NIBUserRepo
from src.nib_user.dto.nib_user_dto import NIBUserDTO
from src.email.dto.report_confirmation_dto import ReportConfirmationDTO
from src.email.query_report_confirmation import RecipientDTO, QueryReportConfirmation
from src.query_queue.query_queue_connection import QueryQueueConnection
from werkzeug.exceptions import BadRequest
from src.queries.enums.exception_message import QueryException


@app.route("/query/<int:query_id>", methods=["GET"])
@jwt_required()
def get_application(query_id: int):
    query: QueryDTO = QueryService().get_query(query_id=query_id)
    return jsonify(query=query), 200


@app.route("/query/query-results/<int:query_id>", methods=["GET"])
@jwt_required()
def get_query_results(query_id: int):
    query_params: dict = {}
    params = request.args
    query_params["query_id"] = query_id
    query_params["page"] = int(params.get("page")) if params.get("page") else 1
    query_params["per_page"] = (
        int(params.get("per_page")) if params.get("per_page") else 10
    )
    try:
        query_params["query_params"] = json.loads(params.get("query_params"))
    except ValueError:
        raise BadRequest(QueryException.QUERY_PARAMS_NOT_SENT.value)

    execute_dto: ExecuteQueryDTO = QueryService().to_execute_query_dto(
        query_params=query_params
    )
    results = QueryService().get_query_results(execute_dto=execute_dto)
    return jsonify(results=results), 200


@app.route("/query/query-report/<int:query_id>", methods=["POST"])
@jwt_required()
def get_query_report(query_id: int):
    query_params: dict = {}
    user_info: dict = {}
    try:
        query_params = json.loads(request.form.get("query_params"))
    except ValueError:
        raise BadRequest(QueryException.QUERY_PARAMS_NOT_SENT.value)

    try:
        user_id = json.loads(request.form.get("user_id"))
    except ValueError:
        raise BadRequest(QueryException.QUERY_USER_NOT_SENT.value)

    query: QueryDTO = QueryService().get_query_report(
        query_id=query_id, params=query_params
    )

    user: NIBUserDTO = NIBUserRepo().find_by_user_id(user_id=user_id)

    if not user:
        raise BadRequest(QueryException.QUERY_USER_DOESENT_EXIST.value)
    elif not user.email:
        raise BadRequest(QueryException.QUERY_USER_EMAIL_DOESNT_EXIST.value)
    else:
        user_info = {"email_address": user.email, "first_name": user.first_name}

    body = json.dumps(query.__dict__ | user_info)

    QueryQueueConnection().channel.basic_publish(
        exchange=Queue.NIB_QUEUE_EXCHANGE,
        routing_key=Queue.QUERY_REPORT_QUEUE,
        body=body,
    )

    data = ReportConfirmationDTO(first_name=user.first_name, query_name=query.name)
    email_recipient = RecipientDTO(email_address=user.email, data=data)
    query_report_confirmation = QueryReportConfirmation()
    query_report_confirmation.send(recipients=[email_recipient])
    return jsonify(query=query), 200


@app.route("/query/query-report/download", methods=["GET"])
def download_query_report():
    try:
        report_id = request.args["report_id"]
    except ValueError:
        raise BadRequest(QueryException.QUERY_REPORT_ID_NOT_SENT.value)
    return send_from_directory(FileRepo.query_reports_path, f"{report_id}.csv")


@app.route("/query/queries-by-user-role", methods=["GET"])
@jwt_required()
def get_queries_by_user_role():
    user = get_jwt_identity()

    user_roles = user["roles"]
    page = request.args.get("page", type=int)
    per_page = request.args.get("per_page", type=int)

    if not page:
        page = 1

    if not per_page:
        per_page = 10

    queries, total = QueryService().get_queries_by_user_role(
        user_roles=user_roles, page=page, per_page=per_page
    )
    return jsonify(total=total, queries=queries), 200
