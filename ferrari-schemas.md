# Ferrari Supply Chain Agents — Data Schema Specification

## Intent

> "Buy all the parts required to assemble a Ferrari in one click."

This document defines every JSON contract in the system: agent identity, messages, backend outputs, and frontend data shapes.

---

## 1. AgentFact Metadata (Registry Schema)

Every agent registers itself with this structure. This is the **DNS record** of the agent network.

```json
{
  "agent_id": "brembo-brake-supplier-01",
  "name": "Brembo S.p.A.",
  "role": "tier_1_supplier",
  "description": "World-leading manufacturer of high-performance braking systems for automotive and motorsport applications.",

  "capabilities": {
    "products": [
      {
        "product_id": "carbon-ceramic-disc-396mm",
        "name": "Carbon Ceramic Brake Disc 396mm",
        "category": "braking_system",
        "subcategory": "disc",
        "specifications": {
          "material": "carbon_ceramic",
          "diameter_mm": 396,
          "weight_kg": 4.2,
          "max_temp_celsius": 1000
        },
        "unit_price_eur": 2800.00,
        "currency": "EUR",
        "min_order_quantity": 50,
        "lead_time_days": 14
      }
    ],
    "services": ["custom_engineering", "oem_supply", "testing_validation"],
    "production_capacity": {
      "units_per_month": 15000,
      "current_utilization_pct": 72
    }
  },

  "identity": {
    "legal_entity": "Brembo S.p.A.",
    "registration_country": "IT",
    "vat_id": "IT00222620163",
    "duns_number": "341234567"
  },

  "certifications": [
    {
      "type": "IATF_16949",
      "description": "Automotive Quality Management System",
      "issued_by": "TÜV SÜD",
      "valid_until": "2026-08-15",
      "status": "active"
    },
    {
      "type": "ISO_14001",
      "description": "Environmental Management System",
      "issued_by": "DNV GL",
      "valid_until": "2026-03-01",
      "status": "active"
    }
  ],

  "location": {
    "headquarters": {
      "city": "Curno",
      "region": "Bergamo",
      "country": "IT",
      "lat": 45.6833,
      "lon": 9.6150
    },
    "manufacturing_sites": [
      {
        "site_id": "brembo-curno-plant",
        "city": "Curno",
        "country": "IT",
        "lat": 45.6833,
        "lon": 9.6150,
        "capabilities": ["casting", "machining", "assembly"]
      }
    ],
    "shipping_regions": ["EU", "NA", "APAC"]
  },

  "compliance": {
    "jurisdictions": ["EU", "IT"],
    "regulations": ["EU_REACH", "EU_ELV_Directive", "CE_Marking"],
    "sanctions_clear": true,
    "esg_rating": {
      "provider": "EcoVadis",
      "score": 72,
      "tier": "Gold",
      "valid_until": "2026-01-01"
    }
  },

  "policies": {
    "payment_terms": "Net 60",
    "incoterms": ["EXW", "DAP", "CIF"],
    "accepted_currencies": ["EUR", "USD"],
    "insurance": {
      "product_liability": true,
      "max_coverage_eur": 50000000
    },
    "min_contract_value_eur": 10000,
    "nda_required": true
  },

  "trust": {
    "trust_score": 0.94,
    "years_in_operation": 63,
    "ferrari_tier_status": "approved_supplier",
    "past_contracts": 847,
    "on_time_delivery_pct": 96.2,
    "defect_rate_ppm": 12,
    "dispute_count_12m": 0
  },

  "network": {
    "endpoint": "http://localhost:8002/agent/brembo-brake-supplier-01",
    "protocol": "HTTP/JSON",
    "api_version": "1.0",
    "supported_message_types": [
      "request_quote",
      "negotiate",
      "purchase_order",
      "shipment_update",
      "disruption_alert"
    ],
    "framework": "plain_python",
    "heartbeat_url": "http://localhost:8002/agent/brembo-brake-supplier-01/status"
  },

  "upstream_dependencies": [
    {
      "material": "Carbon fiber prepreg",
      "typical_supplier_role": "tier_2_supplier",
      "critical": true
    },
    {
      "material": "Aluminum alloy billets",
      "typical_supplier_role": "raw_material_supplier",
      "critical": false
    }
  ],

  "registered_at": "2025-02-07T09:00:00Z",
  "last_heartbeat": "2025-02-07T14:32:00Z",
  "status": "active"
}
```

### Role Enum Values

| Role | Description | Example in Ferrari Context |
|------|-------------|---------------------------|
| `procurement_agent` | Decomposes intent, discovers suppliers, negotiates | Ferrari Purchasing AI |
| `tier_1_supplier` | Supplies finished components directly to OEM | Brembo (brakes), Magneti Marelli (electronics) |
| `tier_2_supplier` | Supplies sub-components to Tier 1 | Carbon fiber producer supplying Brembo |
| `raw_material_supplier` | Supplies raw materials | Aluminum smelter, rubber producer |
| `contract_manufacturer` | Produces to Ferrari spec under contract | Bodywork stamping plant |
| `logistics_provider` | Freight, shipping, warehousing | DHL, Kuehne+Nagel, port operators |
| `compliance_agent` | Validates certs, regs, trade rules | EU compliance validator |
| `assembly_coordinator` | Manages BOM and assembly sequencing | Maranello plant coordinator |

---

## 2. Message Schema (Agent-to-Agent Communication)

Every message in the system follows this envelope format. This is the **TCP packet** of the network.

```json
{
  "message_id": "msg-20250207-143200-a1b2c3",
  "conversation_id": "conv-ferrari-restock-001",
  "timestamp": "2025-02-07T14:32:00Z",
  "from": "ferrari-procurement-01",
  "to": "brembo-brake-supplier-01",
  "type": "request_quote",
  "priority": "normal",
  "payload": {},
  "metadata": {
    "hop_count": 1,
    "origin": "ferrari-procurement-01",
    "trace_path": ["ferrari-procurement-01"]
  }
}
```

### Message Types & Payloads

#### `request_quote`
```json
{
  "type": "request_quote",
  "payload": {
    "items": [
      {
        "product_id": "carbon-ceramic-disc-396mm",
        "product_name": "Carbon Ceramic Brake Disc 396mm",
        "category": "braking_system",
        "quantity": 200,
        "specifications": {
          "material": "carbon_ceramic",
          "diameter_mm": 396,
          "ferrari_part_number": "FE-BRK-0042"
        },
        "required_certifications": ["IATF_16949"],
        "delivery_deadline": "2025-03-15T00:00:00Z",
        "delivery_location": {
          "name": "Ferrari Maranello Plant",
          "city": "Maranello",
          "country": "IT",
          "lat": 44.5294,
          "lon": 10.8633
        }
      }
    ],
    "budget_ceiling_per_unit_eur": 3000.00,
    "incoterms_preference": "DAP"
  }
}
```

#### `quote_response`
```json
{
  "type": "quote_response",
  "payload": {
    "quote_id": "QT-BREMBO-2025-4421",
    "status": "available",
    "items": [
      {
        "product_id": "carbon-ceramic-disc-396mm",
        "quantity_available": 200,
        "unit_price_eur": 2800.00,
        "total_price_eur": 560000.00,
        "lead_time_days": 14,
        "estimated_ship_date": "2025-02-21T00:00:00Z",
        "estimated_delivery_date": "2025-02-24T00:00:00Z"
      }
    ],
    "payment_terms": "Net 60",
    "incoterms": "DAP",
    "valid_until": "2025-02-14T23:59:59Z",
    "notes": "Price reflects existing framework agreement. Expedited delivery possible at 8% surcharge."
  }
}
```

#### `negotiate`
```json
{
  "type": "negotiate",
  "payload": {
    "quote_id": "QT-BREMBO-2025-4421",
    "action": "counter_offer",
    "proposed_changes": {
      "unit_price_eur": 2650.00,
      "reason": "Volume commitment of 200 units warrants 5.4% discount"
    },
    "alternative_terms": {
      "quantity_for_price_break": 300,
      "long_term_contract_months": 12
    }
  }
}
```

#### `negotiate_response`
```json
{
  "type": "negotiate_response",
  "payload": {
    "quote_id": "QT-BREMBO-2025-4421",
    "action": "counter_offer",
    "final_unit_price_eur": 2720.00,
    "conditions": "Price valid for 200+ units with 12-month framework agreement",
    "accepted": false,
    "awaiting_response": true
  }
}
```

#### `purchase_order`
```json
{
  "type": "purchase_order",
  "payload": {
    "po_number": "PO-FERRARI-2025-00891",
    "quote_id": "QT-BREMBO-2025-4421",
    "items": [
      {
        "product_id": "carbon-ceramic-disc-396mm",
        "quantity": 200,
        "agreed_unit_price_eur": 2720.00,
        "total_eur": 544000.00
      }
    ],
    "delivery_deadline": "2025-03-15T00:00:00Z",
    "payment_terms": "Net 60",
    "incoterms": "DAP",
    "ship_to": {
      "name": "Ferrari Maranello Plant",
      "address": "Via Abetone Inferiore 4, 41053 Maranello MO, Italy"
    }
  }
}
```

#### `order_confirmation`
```json
{
  "type": "order_confirmation",
  "payload": {
    "po_number": "PO-FERRARI-2025-00891",
    "status": "confirmed",
    "confirmed_ship_date": "2025-02-21T00:00:00Z",
    "confirmed_delivery_date": "2025-02-24T00:00:00Z",
    "tracking_id": "BREMBO-SHIP-2025-0442"
  }
}
```

#### `logistics_request`
```json
{
  "type": "logistics_request",
  "payload": {
    "shipment_id": "BREMBO-SHIP-2025-0442",
    "origin": {
      "name": "Brembo Curno Plant",
      "city": "Curno",
      "country": "IT",
      "lat": 45.6833,
      "lon": 9.6150
    },
    "destination": {
      "name": "Ferrari Maranello Plant",
      "city": "Maranello",
      "country": "IT",
      "lat": 44.5294,
      "lon": 10.8633
    },
    "cargo": {
      "description": "Carbon ceramic brake discs",
      "pieces": 200,
      "total_weight_kg": 840,
      "total_volume_m3": 4.2,
      "handling": "fragile",
      "temperature_controlled": false,
      "hazmat": false
    },
    "pickup_date": "2025-02-21T00:00:00Z",
    "delivery_deadline": "2025-02-24T00:00:00Z",
    "insurance_required": true
  }
}
```

#### `logistics_proposal`
```json
{
  "type": "logistics_proposal",
  "payload": {
    "shipment_id": "BREMBO-SHIP-2025-0442",
    "route": {
      "mode": "road",
      "legs": [
        {
          "from": "Curno, IT",
          "to": "Maranello, IT",
          "distance_km": 220,
          "duration_hours": 3.5,
          "vehicle_type": "enclosed_truck",
          "carrier": "FrostFreight IT"
        }
      ]
    },
    "cost_eur": 1850.00,
    "pickup_window": "2025-02-21T06:00:00Z / 2025-02-21T12:00:00Z",
    "estimated_delivery": "2025-02-21T18:00:00Z",
    "insurance_included": true,
    "tracking_url": "https://tracking.frostfreight.example/BREMBO-SHIP-2025-0442"
  }
}
```

#### `compliance_check`
```json
{
  "type": "compliance_check",
  "payload": {
    "agent_id": "brembo-brake-supplier-01",
    "checks_requested": [
      "certification_validity",
      "sanctions_screening",
      "esg_threshold",
      "regulation_compliance"
    ],
    "thresholds": {
      "min_esg_score": 50,
      "required_certifications": ["IATF_16949"],
      "required_regulations": ["EU_REACH", "CE_Marking"],
      "banned_jurisdictions": ["RU", "BY", "KP"]
    }
  }
}
```

#### `compliance_result`
```json
{
  "type": "compliance_result",
  "payload": {
    "agent_id": "brembo-brake-supplier-01",
    "overall_status": "approved",
    "checks": [
      {
        "check": "certification_validity",
        "status": "pass",
        "detail": "IATF_16949 valid until 2026-08-15"
      },
      {
        "check": "sanctions_screening",
        "status": "pass",
        "detail": "No matches in EU/US sanctions lists"
      },
      {
        "check": "esg_threshold",
        "status": "pass",
        "detail": "EcoVadis score 72 exceeds minimum 50"
      },
      {
        "check": "regulation_compliance",
        "status": "pass",
        "detail": "EU_REACH and CE_Marking confirmed"
      }
    ],
    "flags": [],
    "approved_at": "2025-02-07T14:35:00Z"
  }
}
```

#### `disruption_alert`
```json
{
  "type": "disruption_alert",
  "payload": {
    "alert_id": "ALERT-2025-0087",
    "severity": "critical",
    "affected_agent": "brembo-brake-supplier-01",
    "disruption_type": "production_halt",
    "reason": "Raw material shortage — carbon fiber supply interrupted",
    "impact": {
      "products_affected": ["carbon-ceramic-disc-396mm"],
      "estimated_delay_days": 21,
      "capacity_remaining_pct": 0
    },
    "recommended_action": "re_source",
    "timestamp": "2025-02-10T08:00:00Z"
  }
}
```

---

## 3. Backend Output — Network Coordination Report

This is the final output the backend produces after a full cascade. Used by the frontend to display results, and exported as a report.

```json
{
  "report_id": "NCR-FERRARI-2025-001",
  "intent": "Buy all parts required to assemble one Ferrari 296 GTB",
  "initiated_by": "ferrari-procurement-01",
  "initiated_at": "2025-02-07T14:00:00Z",
  "completed_at": "2025-02-07T14:38:00Z",
  "status": "completed",

  "bill_of_materials_summary": {
    "total_component_categories": 8,
    "total_unique_parts": 47,
    "categories": [
      {
        "category": "powertrain",
        "parts_count": 12,
        "key_components": ["V6 Engine Block", "Turbocharger Assembly", "8-Speed DCT Gearbox"]
      },
      {
        "category": "braking_system",
        "parts_count": 6,
        "key_components": ["Carbon Ceramic Disc 396mm", "Brake Caliper Set", "Brake Fluid Reservoir"]
      },
      {
        "category": "body_chassis",
        "parts_count": 8,
        "key_components": ["Carbon Fiber Monocoque", "Aluminum Subframe", "Body Panels"]
      },
      {
        "category": "electronics",
        "parts_count": 9,
        "key_components": ["ECU", "Infotainment Unit", "Sensor Array"]
      },
      {
        "category": "interior",
        "parts_count": 5,
        "key_components": ["Leather Seat Assembly", "Steering Wheel", "Dashboard Module"]
      },
      {
        "category": "suspension",
        "parts_count": 4,
        "key_components": ["MagneRide Dampers", "Control Arms", "Anti-Roll Bar"]
      },
      {
        "category": "wheels_tires",
        "parts_count": 2,
        "key_components": ["Forged Alloy Wheels 20\"", "Pirelli P Zero Tires"]
      },
      {
        "category": "exhaust_emissions",
        "parts_count": 1,
        "key_components": ["Catalytic Converter + Exhaust System"]
      }
    ]
  },

  "discovery_results": {
    "agents_discovered": 12,
    "agents_qualified": 8,
    "agents_disqualified": 4,
    "disqualification_reasons": [
      {
        "agent_id": "cheapparts-cn-03",
        "reason": "Failed IATF_16949 certification check"
      },
      {
        "agent_id": "noname-logistics-07",
        "reason": "Trust score 0.31 below threshold 0.70"
      }
    ],
    "discovery_paths": [
      {
        "need": "Carbon Ceramic Brake Disc 396mm",
        "query": "role=tier_1_supplier, capability=braking_system, certification=IATF_16949, region=EU",
        "results_count": 3,
        "selected": "brembo-brake-supplier-01",
        "selection_reason": "Highest trust score (0.94), existing Ferrari approved supplier, competitive pricing"
      },
      {
        "need": "V6 Engine Block",
        "query": "role=tier_1_supplier, capability=powertrain, certification=IATF_16949",
        "results_count": 2,
        "selected": "ferrari-powertrain-internal-01",
        "selection_reason": "In-house production at Maranello, zero logistics cost"
      }
    ]
  },

  "negotiations": [
    {
      "with_agent": "brembo-brake-supplier-01",
      "product": "Carbon Ceramic Brake Disc 396mm",
      "rounds": 3,
      "initial_ask_eur": 2800.00,
      "initial_offer_eur": 2650.00,
      "final_agreed_eur": 2720.00,
      "discount_pct": 2.86,
      "negotiation_log": [
        {
          "round": 1,
          "from": "ferrari-procurement-01",
          "action": "counter_offer",
          "value_eur": 2650.00,
          "reasoning": "Volume commitment of 200 units warrants ~5% discount"
        },
        {
          "round": 2,
          "from": "brembo-brake-supplier-01",
          "action": "counter_offer",
          "value_eur": 2750.00,
          "reasoning": "Can offer 1.8% discount, carbon fiber costs limit flexibility"
        },
        {
          "round": 3,
          "from": "ferrari-procurement-01",
          "action": "accept",
          "value_eur": 2720.00,
          "reasoning": "Split the difference, within budget ceiling of €3000"
        }
      ]
    }
  ],

  "compliance_summary": {
    "total_checks": 8,
    "passed": 7,
    "flagged": 1,
    "failed": 0,
    "flags": [
      {
        "agent_id": "tier2-rubber-supplier-04",
        "check": "esg_threshold",
        "detail": "EcoVadis score 52 — marginally above minimum 50, recommend monitoring",
        "severity": "warning"
      }
    ]
  },

  "logistics_plan": {
    "total_shipments": 6,
    "total_logistics_cost_eur": 18400.00,
    "shipments": [
      {
        "shipment_id": "SHIP-001",
        "from_agent": "brembo-brake-supplier-01",
        "from_location": "Curno, IT",
        "to_location": "Maranello, IT",
        "cargo": "Brake system components",
        "mode": "road",
        "distance_km": 220,
        "cost_eur": 1850.00,
        "pickup_date": "2025-02-21",
        "delivery_date": "2025-02-21",
        "carrier": "FrostFreight IT",
        "status": "scheduled"
      }
    ],
    "critical_path_days": 18,
    "bottleneck": "Carbon fiber monocoque — 18 day lead time from Dallara Compositi"
  },

  "execution_plan": {
    "total_cost_eur": 187450.00,
    "cost_breakdown": {
      "components_eur": 164200.00,
      "logistics_eur": 18400.00,
      "insurance_eur": 3200.00,
      "compliance_fees_eur": 1650.00
    },
    "timeline": {
      "procurement_start": "2025-02-07",
      "all_components_ordered": "2025-02-08",
      "first_delivery": "2025-02-14",
      "last_delivery": "2025-02-25",
      "assembly_ready": "2025-02-25"
    },
    "suppliers_engaged": 8,
    "purchase_orders_issued": 8,
    "risk_assessment": {
      "overall_risk": "medium",
      "risks": [
        {
          "type": "single_source_dependency",
          "component": "Carbon Fiber Monocoque",
          "supplier": "dallara-compositi-01",
          "mitigation": "Alternative supplier identified: carbon-tech-de-02 (21-day lead time)"
        },
        {
          "type": "lead_time",
          "component": "MagneRide Dampers",
          "detail": "16-day lead time, 2-day buffer to assembly deadline",
          "mitigation": "Expedited shipping option available at +€800"
        }
      ]
    }
  },

  "disruptions_handled": [
    {
      "alert_id": "ALERT-2025-0087",
      "timestamp": "2025-02-10T08:00:00Z",
      "disrupted_agent": "brembo-brake-supplier-01",
      "disruption_type": "production_halt",
      "resolution": {
        "action": "re_source",
        "new_supplier": "performance-friction-us-01",
        "new_price_eur": 2950.00,
        "additional_cost_eur": 46000.00,
        "delay_days": 3,
        "resolved_at": "2025-02-10T08:04:32Z"
      }
    }
  ],

  "message_log_summary": {
    "total_messages": 47,
    "by_type": {
      "request_quote": 8,
      "quote_response": 8,
      "negotiate": 5,
      "negotiate_response": 5,
      "compliance_check": 8,
      "compliance_result": 8,
      "purchase_order": 8,
      "order_confirmation": 8,
      "logistics_request": 6,
      "logistics_proposal": 6,
      "disruption_alert": 1
    },
    "full_log_url": "/logs/messages.jsonl"
  }
}
```

---

## 4. Frontend Data — What the Dashboard Consumes

### 4a. Supply Network Graph

```json
{
  "nodes": [
    {
      "id": "ferrari-procurement-01",
      "label": "Ferrari Procurement",
      "role": "procurement_agent",
      "color": "#DC143C",
      "location": { "lat": 44.5294, "lon": 10.8633, "city": "Maranello" },
      "trust_score": null,
      "status": "active",
      "size": 40
    },
    {
      "id": "brembo-brake-supplier-01",
      "label": "Brembo S.p.A.",
      "role": "tier_1_supplier",
      "color": "#2196F3",
      "location": { "lat": 45.6833, "lon": 9.6150, "city": "Curno" },
      "trust_score": 0.94,
      "status": "active",
      "size": 30
    },
    {
      "id": "compliance-agent-01",
      "label": "EU Compliance Validator",
      "role": "compliance_agent",
      "color": "#FF9800",
      "location": null,
      "trust_score": null,
      "status": "active",
      "size": 25
    }
  ],
  "edges": [
    {
      "from": "ferrari-procurement-01",
      "to": "brembo-brake-supplier-01",
      "type": "procurement",
      "label": "PO-FERRARI-2025-00891",
      "value_eur": 544000.00,
      "message_count": 6,
      "status": "confirmed"
    },
    {
      "from": "ferrari-procurement-01",
      "to": "compliance-agent-01",
      "type": "compliance",
      "label": "Validation request",
      "message_count": 2,
      "status": "completed"
    },
    {
      "from": "brembo-brake-supplier-01",
      "to": "dhl-logistics-01",
      "type": "logistics",
      "label": "SHIP-001",
      "message_count": 2,
      "status": "scheduled"
    }
  ],
  "color_legend": {
    "procurement_agent": "#DC143C",
    "tier_1_supplier": "#2196F3",
    "tier_2_supplier": "#64B5F6",
    "raw_material_supplier": "#90CAF9",
    "contract_manufacturer": "#4CAF50",
    "logistics_provider": "#9C27B0",
    "compliance_agent": "#FF9800",
    "assembly_coordinator": "#F44336"
  }
}
```

### 4b. Live Message Feed

```json
{
  "messages": [
    {
      "message_id": "msg-001",
      "timestamp": "2025-02-07T14:00:01Z",
      "from": "ferrari-procurement-01",
      "from_label": "Ferrari Procurement",
      "to": "registry",
      "to_label": "Agent Registry",
      "type": "discovery",
      "summary": "Searching for tier_1_supplier with braking_system capability in EU",
      "detail": "Query: role=tier_1_supplier, capability=braking_system, certification=IATF_16949, region=EU → 3 results",
      "color": "#2196F3",
      "icon": "search"
    },
    {
      "message_id": "msg-002",
      "timestamp": "2025-02-07T14:00:03Z",
      "from": "ferrari-procurement-01",
      "from_label": "Ferrari Procurement",
      "to": "brembo-brake-supplier-01",
      "to_label": "Brembo S.p.A.",
      "type": "request_quote",
      "summary": "Requesting quote for 200x Carbon Ceramic Brake Disc 396mm",
      "detail": "Budget ceiling: €3,000/unit. Delivery by 2025-03-15 to Maranello.",
      "color": "#4CAF50",
      "icon": "request"
    },
    {
      "message_id": "msg-003",
      "timestamp": "2025-02-07T14:00:08Z",
      "from": "brembo-brake-supplier-01",
      "from_label": "Brembo S.p.A.",
      "to": "ferrari-procurement-01",
      "to_label": "Ferrari Procurement",
      "type": "quote_response",
      "summary": "Quoted €2,800/unit, 14-day lead time, delivery by Feb 24",
      "detail": "Total: €560,000. Payment: Net 60. Valid until Feb 14.",
      "color": "#4CAF50",
      "icon": "response"
    },
    {
      "message_id": "msg-disruption",
      "timestamp": "2025-02-10T08:00:00Z",
      "from": "brembo-brake-supplier-01",
      "from_label": "Brembo S.p.A.",
      "to": "ferrari-procurement-01",
      "to_label": "Ferrari Procurement",
      "type": "disruption_alert",
      "summary": "⚠️ PRODUCTION HALT — Carbon fiber supply interrupted",
      "detail": "Estimated 21-day delay. Capacity at 0%. Recommended action: re-source.",
      "color": "#F44336",
      "icon": "alert"
    }
  ]
}
```

### 4c. Execution Dashboard Cards

```json
{
  "dashboard": {
    "hero_metrics": [
      { "label": "Total Cost", "value": "€187,450", "trend": null },
      { "label": "Suppliers Engaged", "value": "8", "trend": null },
      { "label": "Time to Assembly-Ready", "value": "18 days", "trend": null },
      { "label": "Compliance Pass Rate", "value": "100%", "trend": "up" },
      { "label": "Disruptions Resolved", "value": "1/1", "trend": null },
      { "label": "Messages Exchanged", "value": "47", "trend": null }
    ],

    "cost_breakdown_chart": {
      "type": "donut",
      "data": [
        { "label": "Components", "value": 164200, "color": "#2196F3" },
        { "label": "Logistics", "value": 18400, "color": "#9C27B0" },
        { "label": "Insurance", "value": 3200, "color": "#FF9800" },
        { "label": "Compliance", "value": 1650, "color": "#4CAF50" }
      ]
    },

    "timeline_chart": {
      "type": "gantt",
      "items": [
        {
          "label": "Brake System (Brembo)",
          "start": "2025-02-07",
          "end": "2025-02-21",
          "status": "confirmed",
          "category": "braking_system"
        },
        {
          "label": "Carbon Monocoque (Dallara)",
          "start": "2025-02-07",
          "end": "2025-02-25",
          "status": "confirmed",
          "critical_path": true,
          "category": "body_chassis"
        },
        {
          "label": "Electronics (Magneti Marelli)",
          "start": "2025-02-07",
          "end": "2025-02-17",
          "status": "confirmed",
          "category": "electronics"
        }
      ]
    },

    "supplier_map": {
      "type": "geo_map",
      "center": { "lat": 45.0, "lon": 10.0 },
      "zoom": 6,
      "markers": [
        {
          "lat": 44.5294,
          "lon": 10.8633,
          "label": "Ferrari Maranello (Assembly)",
          "type": "destination",
          "color": "#DC143C"
        },
        {
          "lat": 45.6833,
          "lon": 9.6150,
          "label": "Brembo (Brakes)",
          "type": "supplier",
          "color": "#2196F3"
        }
      ],
      "routes": [
        {
          "from": { "lat": 45.6833, "lon": 9.6150 },
          "to": { "lat": 44.5294, "lon": 10.8633 },
          "label": "Brembo → Maranello",
          "mode": "road",
          "distance_km": 220
        }
      ]
    },

    "risk_panel": {
      "overall": "medium",
      "items": [
        {
          "severity": "high",
          "type": "Single Source",
          "component": "Carbon Fiber Monocoque",
          "supplier": "Dallara Compositi",
          "detail": "No backup supplier within 18-day lead time"
        },
        {
          "severity": "low",
          "type": "Lead Time",
          "component": "MagneRide Dampers",
          "supplier": "Magneti Marelli",
          "detail": "2-day buffer, expedite option available"
        }
      ]
    },

    "agent_reasoning_log": [
      {
        "agent": "Ferrari Procurement",
        "timestamp": "2025-02-07T14:00:01Z",
        "thought": "Decomposing intent: Ferrari 296 GTB requires 8 component categories. Starting with critical path items — body/chassis has longest lead time, sourcing first."
      },
      {
        "agent": "Ferrari Procurement",
        "timestamp": "2025-02-07T14:00:05Z",
        "thought": "3 brake suppliers found. Brembo has highest trust score (0.94) and is an existing approved supplier. Selecting Brembo for quote request despite marginally higher price than alternatives."
      },
      {
        "agent": "Brembo S.p.A.",
        "timestamp": "2025-02-07T14:00:08Z",
        "thought": "Ferrari RFQ received for 200 brake discs. Current utilization 72%, capacity available. Quoting standard OEM price €2,800. Expecting counter-offer — floor price is €2,680 at 4.3% margin."
      },
      {
        "agent": "Ferrari Procurement",
        "timestamp": "2025-02-07T14:00:10Z",
        "thought": "Brembo quoted €2,800 — within budget ceiling of €3,000 but I'll negotiate. Offering €2,650 citing volume. Willing to settle at €2,720 which saves €16,000 on order."
      }
    ]
  }
}
```

---

## 5. Registry API Endpoints (for reference)

```
POST   /registry/register          → body: AgentFact → 201
GET    /registry/search            → ?role=X&capability=Y&region=Z&certification=W → AgentFact[]
GET    /registry/list              → AgentFact[]
GET    /registry/agent/{agent_id}  → AgentFact
DELETE /registry/deregister/{id}   → 204
POST   /registry/log               → body: Message → 201
GET    /registry/logs              → Message[]
POST   /registry/trigger           → body: {intent, budget} → kicks off cascade
POST   /registry/disrupt/{agent_id} → simulates disruption
```

---

## Quick Reference: Who Produces / Consumes What

| Data Structure | Produced By | Consumed By |
|---------------|-------------|-------------|
| AgentFact | Person 3 (supplier agents) + Person 2 (buyer agents) | Person 1 (registry), Person 4 (dashboard) |
| Messages | Person 2 + Person 3 (all agent communication) | Person 1 (logger), Person 4 (live feed) |
| Network Coordination Report | Person 1 (backend aggregation) | Person 4 (dashboard summary) |
| Graph nodes/edges | Person 4 (transforms registry + logs) | Person 4 (renders) |
| Dashboard cards | Person 4 (transforms report) | Person 4 (renders) |
