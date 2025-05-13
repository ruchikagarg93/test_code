from src.pr_flyers_metrics_worker.worker.worker.request import CisRequestUp

# Sample request input
request_data = {
    "application": "projectrun",
    "consumer": "promoflyers",
    "country": "us",
    "characteristics": [
        "promoflyers-metrics"
    ],
    "client": "GLT",
    "input": {
        "assets": [
            {
                "name": "test_name",
                "path":"/projectrun/promoflyers/input/REQ-db0b6564-fe43-408b-9c9c-9391d1d64a4e/metic_example.csv",
                "delimiter": ",",
                "iso_week": 202501
            }
        ]
    }
}

req = CisRequestUp(**request_data)
worker.run(req, output_path, feedback_container)
