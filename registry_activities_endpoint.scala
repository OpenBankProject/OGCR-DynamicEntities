/*
 * Method body for the OGCR registry activities Dynamic Resource Doc.
 *
 * This file is the readable source of truth. `dynamic_resource_docs.py` reads it,
 * URL-encodes it and PUTs/POSTs it as the `method_body` field — the API stores the
 * code URL-encoded inside a JSON column, which is unreviewable in that form, so the
 * repo keeps the real Scala here and encodes at push time.
 *
 * Served at:  GET /obp/dynamic-endpoint/registry/activities
 * Auth:       none (the doc is created with no `roles`, so authentication is optional)
 *
 * Why an endpoint rather than five client-side calls: the registry list needs
 * activity joined to operator, country, certificate_of_compliance and
 * activity_verification. Doing that in the browser/app means five round trips and
 * ships every field of every entity to the client. Here the join happens next to the
 * data and only the registry columns are projected — which matters because this
 * endpoint is public.
 *
 * System-level entities only (bankId = None). Bank/space-level versioning is
 * deliberately not used yet — see SPACE_LEVEL_VERSIONING_PLAN.md.
 *
 * What is in scope without importing: CallContext, HttpCode, IO, Request/Response,
 * Future, the global ExecutionContext and `implicit val formats`, all supplied by
 * DynamicCompileEndpoint. Everything else must be imported inside the body, which is
 * what the block below does. The last expression is an OBPReturnType, converted to an
 * IO[Response[IO]] by DynamicCompileEndpoint.obpReturnTypeToIOResponse; the value is
 * rendered with Extraction.decompose, so returning a JValue passes straight through.
 */

    import code.DynamicData.DynamicDataProvider
    import org.json4s.JsonAST.{JArray, JField, JInt, JNull, JObject, JString, JValue}

    val provider = DynamicDataProvider.connectorMethodProvider.vend

    // Entity names as created by parse_minimum_fields.py. If OBP_ENTITY_PREFIX is
    // ever set for a deployment, these need the same prefix.
    val ACTIVITY = "activity"
    val OPERATOR = "operator"
    val COUNTRY = "country"
    val CERTIFICATE = "certificate_of_compliance"
    val VERIFICATION = "activity_verification"

    // bankId = None is the system level; userId = None / isPersonalEntity = false
    // reads the shared rows rather than one user's personal ones.
    def rowsOf(entityName: String): List[JObject] =
      provider.getAllDataJson(None, entityName, None, false)

    def str(row: JObject, field: String): Option[String] =
      row \ field match {
        case JString(s) if s.trim.nonEmpty => Some(s)
        case _ => None
      }

    def jstr(value: Option[String]): JValue = value.map(JString(_)).getOrElse(JNull)

    val activities = rowsOf(ACTIVITY)
    val operators = rowsOf(OPERATOR)
    val countries = rowsOf(COUNTRY)
    val certificates = rowsOf(CERTIFICATE)
    val verifications = rowsOf(VERIFICATION)

    val operatorNameById: Map[String, String] = operators.flatMap { o =>
      for (id <- str(o, "operator_id"); name <- str(o, "legal_name")) yield id -> name
    }.toMap

    val countryNameById: Map[String, String] = countries.flatMap { c =>
      for (id <- str(c, "country_id"); name <- str(c, "country_name")) yield id -> name
    }.toMap

    // certificate_of_compliance is its own entity, joined on activity_id. An activity
    // with no certificate is normal (not yet certified), so this is a left join.
    val certificateByActivityId: Map[String, JObject] =
      certificates.flatMap(c => str(c, "activity_id").map(_ -> c)).toMap

    // The registry shows the same verified/unverified split as the internal
    // Activities page: an activity is verified when it has an activity_verification
    // row whose status_code is "verified".
    val verifiedActivityIds: Set[String] =
      verifications
        .filter(v => str(v, "status_code").contains("verified"))
        .flatMap(v => str(v, "activity_id"))
        .toSet

    val registryRows: List[JValue] = activities.map { activity =>
      val activityId = str(activity, "activity_id")
      val certificate = activityId.flatMap(certificateByActivityId.get)
      val countryId = str(activity, "country_id")
      val operatorId = str(activity, "operator_id")

      JObject(
        List(
          JField("activity_id", jstr(activityId)),
          JField("name", jstr(str(activity, "name"))),
          JField("summary", jstr(str(activity, "summary"))),
          JField("activity_type", jstr(str(activity, "activity_type"))),
          JField("country_id", jstr(countryId)),
          JField("country_name", jstr(countryId.flatMap(countryNameById.get))),
          JField("city", jstr(str(activity, "city"))),
          JField("start_date", jstr(str(activity, "start_date"))),
          JField("end_date", jstr(str(activity, "end_date"))),
          JField("monitoring_period_start_date", jstr(str(activity, "monitoring_period_start_date"))),
          JField("monitoring_period_end_date", jstr(str(activity, "monitoring_period_end_date"))),
          JField("operator_id", jstr(operatorId)),
          JField("operator_legal_name", jstr(operatorId.flatMap(operatorNameById.get))),
          JField(
            "verification_status",
            JString(if (activityId.exists(verifiedActivityIds.contains)) "verified" else "unverified")
          ),
          JField(
            "certificate_of_compliance_id",
            jstr(certificate.flatMap(str(_, "certificate_of_compliance_id")))
          ),
          JField("certification_status", jstr(certificate.flatMap(str(_, "certification_status")))),
          JField("certificate_issue_date", jstr(certificate.flatMap(str(_, "issue_date")))),
          JField("certificate_expiry_date", jstr(certificate.flatMap(str(_, "expiry_date"))))
        )
      )
    }

    val responseBody: JValue =
      JObject(List(JField("activities", JArray(registryRows)), JField("count", JInt(registryRows.size))))

    Future.successful {
      (responseBody, HttpCode.`200`(callContext.callContext))
    }
