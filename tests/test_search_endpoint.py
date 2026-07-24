def test_search_valid_query(test_client):
    response = test_client.post(
        "/api/v1/search",
        json={"query": "برای تولد دوستم یه کلیپ میخوام"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "results" in data


def test_search_chat_like_blocked(test_client):
    response = test_client.post(
        "/api/v1/search",
        json={"query": "خیلی خری میدونستی؟"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] in ["blocked_by_firewall", "validation_error"]