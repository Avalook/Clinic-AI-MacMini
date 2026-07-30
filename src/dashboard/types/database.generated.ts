export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  graphql_public: {
    Tables: {
      [_ in never]: never
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      graphql: {
        Args: {
          extensions?: Json
          operationName?: string
          query?: string
          variables?: Json
        }
        Returns: Json
      }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
  public: {
    Tables: {
      appointment: {
        Row: {
          assigned_station: string | null
          booking_channel: string | null
          cancellation_reason: string | null
          cancelled_at: string | null
          clinic_patient_id: string
          confirmed_at: string | null
          created_at: string | null
          doctor_id: string | null
          episode_id: string | null
          id: string
          is_priority_slot: boolean
          is_walkin: boolean
          location_id: string
          need_sono: boolean | null
          patient_kind: string | null
          queue_number: string | null
          service_type_id: string
          slot_end: string
          slot_start: string
          sono_min: number | null
          status: string
          thanh_min: number | null
          updated_at: string | null
          work_session_id: string | null
        }
        Insert: {
          assigned_station?: string | null
          booking_channel?: string | null
          cancellation_reason?: string | null
          cancelled_at?: string | null
          clinic_patient_id: string
          confirmed_at?: string | null
          created_at?: string | null
          doctor_id?: string | null
          episode_id?: string | null
          id?: string
          is_priority_slot?: boolean
          is_walkin?: boolean
          location_id: string
          need_sono?: boolean | null
          patient_kind?: string | null
          queue_number?: string | null
          service_type_id: string
          slot_end: string
          slot_start: string
          sono_min?: number | null
          status?: string
          thanh_min?: number | null
          updated_at?: string | null
          work_session_id?: string | null
        }
        Update: {
          assigned_station?: string | null
          booking_channel?: string | null
          cancellation_reason?: string | null
          cancelled_at?: string | null
          clinic_patient_id?: string
          confirmed_at?: string | null
          created_at?: string | null
          doctor_id?: string | null
          episode_id?: string | null
          id?: string
          is_priority_slot?: boolean
          is_walkin?: boolean
          location_id?: string
          need_sono?: boolean | null
          patient_kind?: string | null
          queue_number?: string | null
          service_type_id?: string
          slot_end?: string
          slot_start?: string
          sono_min?: number | null
          status?: string
          thanh_min?: number | null
          updated_at?: string | null
          work_session_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "appointment_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "appointment_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient_summary"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "appointment_doctor_id_fkey"
            columns: ["doctor_id"]
            isOneToOne: false
            referencedRelation: "staff"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "appointment_episode_id_fkey"
            columns: ["episode_id"]
            isOneToOne: false
            referencedRelation: "care_episode"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "appointment_location_id_fkey"
            columns: ["location_id"]
            isOneToOne: false
            referencedRelation: "clinic_location"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "appointment_service_type_id_fkey"
            columns: ["service_type_id"]
            isOneToOne: false
            referencedRelation: "service_type"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "appointment_work_session_id_fkey"
            columns: ["work_session_id"]
            isOneToOne: false
            referencedRelation: "work_session"
            referencedColumns: ["id"]
          },
        ]
      }
      block_budget: {
        Row: {
          buffer_min: number
          created_at: string
          doctor_id: string | null
          hour_start: number
          id: string
          location_id: string
          max_total: number
          new_cap: number
          online_quota_min: number
          sono_budget_min: number
          thanh_budget_min: number
          updated_at: string
          walkin_quota_min: number
          weekday: number | null
        }
        Insert: {
          buffer_min?: number
          created_at?: string
          doctor_id?: string | null
          hour_start: number
          id?: string
          location_id: string
          max_total?: number
          new_cap?: number
          online_quota_min?: number
          sono_budget_min?: number
          thanh_budget_min?: number
          updated_at?: string
          walkin_quota_min?: number
          weekday?: number | null
        }
        Update: {
          buffer_min?: number
          created_at?: string
          doctor_id?: string | null
          hour_start?: number
          id?: string
          location_id?: string
          max_total?: number
          new_cap?: number
          online_quota_min?: number
          sono_budget_min?: number
          thanh_budget_min?: number
          updated_at?: string
          walkin_quota_min?: number
          weekday?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "block_budget_doctor_id_fkey"
            columns: ["doctor_id"]
            isOneToOne: false
            referencedRelation: "staff"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "block_budget_location_id_fkey"
            columns: ["location_id"]
            isOneToOne: false
            referencedRelation: "clinic_location"
            referencedColumns: ["id"]
          },
        ]
      }
      booking_channel: {
        Row: {
          category: string
          code: string
          created_at: string | null
          id: string
          is_active: boolean
          name: string
        }
        Insert: {
          category: string
          code: string
          created_at?: string | null
          id?: string
          is_active?: boolean
          name: string
        }
        Update: {
          category?: string
          code?: string
          created_at?: string | null
          id?: string
          is_active?: boolean
          name?: string
        }
        Relationships: []
      }
      care_episode: {
        Row: {
          clinic_patient_id: string
          close_reason: string | null
          closed_at: string | null
          created_at: string
          id: string
          last_visit_at: string | null
          opened_appointment_id: string | null
          opened_at: string
          service_type_id: string
          status: string
          updated_at: string
        }
        Insert: {
          clinic_patient_id: string
          close_reason?: string | null
          closed_at?: string | null
          created_at?: string
          id?: string
          last_visit_at?: string | null
          opened_appointment_id?: string | null
          opened_at?: string
          service_type_id: string
          status?: string
          updated_at?: string
        }
        Update: {
          clinic_patient_id?: string
          close_reason?: string | null
          closed_at?: string | null
          created_at?: string
          id?: string
          last_visit_at?: string | null
          opened_appointment_id?: string | null
          opened_at?: string
          service_type_id?: string
          status?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "care_episode_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "care_episode_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient_summary"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "care_episode_opened_appointment_id_fkey"
            columns: ["opened_appointment_id"]
            isOneToOne: false
            referencedRelation: "appointment"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "care_episode_service_type_id_fkey"
            columns: ["service_type_id"]
            isOneToOne: false
            referencedRelation: "service_type"
            referencedColumns: ["id"]
          },
        ]
      }
      clinic_location: {
        Row: {
          address: string | null
          code: string
          created_at: string | null
          id: string
          is_active: boolean | null
          name: string
        }
        Insert: {
          address?: string | null
          code: string
          created_at?: string | null
          id?: string
          is_active?: boolean | null
          name: string
        }
        Update: {
          address?: string | null
          code?: string
          created_at?: string | null
          id?: string
          is_active?: boolean | null
          name?: string
        }
        Relationships: []
      }
      clinical_form_response: {
        Row: {
          created_at: string
          created_by: string | null
          form_data: Json
          id: string
          service_code: string
          updated_at: string
          updated_by: string | null
          visit_id: string
        }
        Insert: {
          created_at?: string
          created_by?: string | null
          form_data?: Json
          id?: string
          service_code: string
          updated_at?: string
          updated_by?: string | null
          visit_id: string
        }
        Update: {
          created_at?: string
          created_by?: string | null
          form_data?: Json
          id?: string
          service_code?: string
          updated_at?: string
          updated_by?: string | null
          visit_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "clinical_form_response_visit_id_fkey"
            columns: ["visit_id"]
            isOneToOne: false
            referencedRelation: "visit"
            referencedColumns: ["visit_id"]
          },
        ]
      }
      clinical_record: {
        Row: {
          chief_complaint_at_visit: string | null
          created_at: string
          pregnancy_id: string | null
          record_id: string
          soap_assessment: Json | null
          soap_objective: Json | null
          soap_plan: Json | null
          soap_subjective: Json | null
          updated_at: string
          visit_id: string
          voice_note_reviewed: boolean
          voice_note_url: string | null
          voice_transcript: string | null
        }
        Insert: {
          chief_complaint_at_visit?: string | null
          created_at?: string
          pregnancy_id?: string | null
          record_id?: string
          soap_assessment?: Json | null
          soap_objective?: Json | null
          soap_plan?: Json | null
          soap_subjective?: Json | null
          updated_at?: string
          visit_id: string
          voice_note_reviewed?: boolean
          voice_note_url?: string | null
          voice_transcript?: string | null
        }
        Update: {
          chief_complaint_at_visit?: string | null
          created_at?: string
          pregnancy_id?: string | null
          record_id?: string
          soap_assessment?: Json | null
          soap_objective?: Json | null
          soap_plan?: Json | null
          soap_subjective?: Json | null
          updated_at?: string
          visit_id?: string
          voice_note_reviewed?: boolean
          voice_note_url?: string | null
          voice_transcript?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "clinical_record_pregnancy_id_fkey"
            columns: ["pregnancy_id"]
            isOneToOne: false
            referencedRelation: "pregnancy"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "clinical_record_visit_id_fkey"
            columns: ["visit_id"]
            isOneToOne: true
            referencedRelation: "visit"
            referencedColumns: ["visit_id"]
          },
        ]
      }
      cskh_action: {
        Row: {
          action_data: string | null
          appointment_link_raw: string | null
          billing_tag: string | null
          category: string | null
          clinic_patient_id: string | null
          created_at: string | null
          created_by_text: string | null
          deadline_at: string | null
          description: string | null
          id: string
          lab_link_raw: string | null
          last_edited_by_text: string | null
          patient_link_raw: string | null
          rating: number | null
          result_text: string | null
          source_created_at: string | null
          source_ref: string
          source_updated_at: string | null
          status: string | null
          step: string | null
          updated_at: string | null
          visit_link_raw: string | null
        }
        Insert: {
          action_data?: string | null
          appointment_link_raw?: string | null
          billing_tag?: string | null
          category?: string | null
          clinic_patient_id?: string | null
          created_at?: string | null
          created_by_text?: string | null
          deadline_at?: string | null
          description?: string | null
          id?: string
          lab_link_raw?: string | null
          last_edited_by_text?: string | null
          patient_link_raw?: string | null
          rating?: number | null
          result_text?: string | null
          source_created_at?: string | null
          source_ref: string
          source_updated_at?: string | null
          status?: string | null
          step?: string | null
          updated_at?: string | null
          visit_link_raw?: string | null
        }
        Update: {
          action_data?: string | null
          appointment_link_raw?: string | null
          billing_tag?: string | null
          category?: string | null
          clinic_patient_id?: string | null
          created_at?: string | null
          created_by_text?: string | null
          deadline_at?: string | null
          description?: string | null
          id?: string
          lab_link_raw?: string | null
          last_edited_by_text?: string | null
          patient_link_raw?: string | null
          rating?: number | null
          result_text?: string | null
          source_created_at?: string | null
          source_ref?: string
          source_updated_at?: string | null
          status?: string | null
          step?: string | null
          updated_at?: string | null
          visit_link_raw?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "cskh_action_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "cskh_action_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient_summary"
            referencedColumns: ["clinic_patient_id"]
          },
        ]
      }
      cskh_log: {
        Row: {
          arrived: boolean | null
          clinic_patient_id: string | null
          confirmed: boolean | null
          confirmed_by: string | null
          created_at: string | null
          cskh_by: string | null
          cskh_followup: string | null
          cskh_status: string | null
          has_test: boolean | null
          id: string
          last_cskh_date: string | null
          note: string | null
          patient_info: string | null
          phone: string | null
          result_eta: string | null
          result_group: string | null
          slot_time: string | null
          source_month: string | null
          tests: string | null
          visit_number: string | null
          visit_type: string | null
          work_date: string | null
        }
        Insert: {
          arrived?: boolean | null
          clinic_patient_id?: string | null
          confirmed?: boolean | null
          confirmed_by?: string | null
          created_at?: string | null
          cskh_by?: string | null
          cskh_followup?: string | null
          cskh_status?: string | null
          has_test?: boolean | null
          id?: string
          last_cskh_date?: string | null
          note?: string | null
          patient_info?: string | null
          phone?: string | null
          result_eta?: string | null
          result_group?: string | null
          slot_time?: string | null
          source_month?: string | null
          tests?: string | null
          visit_number?: string | null
          visit_type?: string | null
          work_date?: string | null
        }
        Update: {
          arrived?: boolean | null
          clinic_patient_id?: string | null
          confirmed?: boolean | null
          confirmed_by?: string | null
          created_at?: string | null
          cskh_by?: string | null
          cskh_followup?: string | null
          cskh_status?: string | null
          has_test?: boolean | null
          id?: string
          last_cskh_date?: string | null
          note?: string | null
          patient_info?: string | null
          phone?: string | null
          result_eta?: string | null
          result_group?: string | null
          slot_time?: string | null
          source_month?: string | null
          tests?: string | null
          visit_number?: string | null
          visit_type?: string | null
          work_date?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "cskh_log_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "cskh_log_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient_summary"
            referencedColumns: ["clinic_patient_id"]
          },
        ]
      }
      drug_catalog: {
        Row: {
          created_at: string | null
          group_label: string | null
          id: string
          is_active: boolean
          name_base: string
          name_raw: string
          needs_review: boolean
          unit_price: number | null
          variant: string | null
        }
        Insert: {
          created_at?: string | null
          group_label?: string | null
          id?: string
          is_active?: boolean
          name_base: string
          name_raw: string
          needs_review?: boolean
          unit_price?: number | null
          variant?: string | null
        }
        Update: {
          created_at?: string | null
          group_label?: string | null
          id?: string
          is_active?: boolean
          name_base?: string
          name_raw?: string
          needs_review?: boolean
          unit_price?: number | null
          variant?: string | null
        }
        Relationships: []
      }
      event_log: {
        Row: {
          aggregate_id: string
          aggregate_type: string
          causation_id: string | null
          correlation_id: string | null
          event_id: string
          event_published: boolean
          event_type: string
          event_version: number
          metadata: Json
          occurred_at: string
          payload: Json
          recorded_at: string
          source: string
        }
        Insert: {
          aggregate_id: string
          aggregate_type: string
          causation_id?: string | null
          correlation_id?: string | null
          event_id?: string
          event_published?: boolean
          event_type: string
          event_version?: number
          metadata?: Json
          occurred_at?: string
          payload: Json
          recorded_at?: string
          source: string
        }
        Update: {
          aggregate_id?: string
          aggregate_type?: string
          causation_id?: string | null
          correlation_id?: string | null
          event_id?: string
          event_published?: boolean
          event_type?: string
          event_version?: number
          metadata?: Json
          occurred_at?: string
          payload?: Json
          recorded_at?: string
          source?: string
        }
        Relationships: [
          {
            foreignKeyName: "event_log_causation_id_fkey"
            columns: ["causation_id"]
            isOneToOne: false
            referencedRelation: "event_log"
            referencedColumns: ["event_id"]
          },
        ]
      }
      lab_result: {
        Row: {
          appointment_id: string | null
          clinic_patient_id: string
          created_at: string
          external_ref: string | null
          flag: string | null
          is_finalized: boolean
          lab_provider: string | null
          lab_result_id: string
          panel_code: string | null
          raw_payload: Json | null
          reference_range_high: number | null
          reference_range_low: number | null
          requires_doctor_review: boolean
          result_numeric: number | null
          result_received_at: string
          result_unit: string | null
          result_value: string | null
          reviewed_at: string | null
          reviewed_by_staff_id: string | null
          sample_collected_at: string | null
          test_code: string
          test_name: string
          triage_classified_at: string | null
          triage_group: string
          triage_model: string | null
          triage_reason: string | null
          updated_at: string
          visit_id: string | null
        }
        Insert: {
          appointment_id?: string | null
          clinic_patient_id: string
          created_at?: string
          external_ref?: string | null
          flag?: string | null
          is_finalized?: boolean
          lab_provider?: string | null
          lab_result_id?: string
          panel_code?: string | null
          raw_payload?: Json | null
          reference_range_high?: number | null
          reference_range_low?: number | null
          requires_doctor_review?: boolean
          result_numeric?: number | null
          result_received_at?: string
          result_unit?: string | null
          result_value?: string | null
          reviewed_at?: string | null
          reviewed_by_staff_id?: string | null
          sample_collected_at?: string | null
          test_code: string
          test_name: string
          triage_classified_at?: string | null
          triage_group?: string
          triage_model?: string | null
          triage_reason?: string | null
          updated_at?: string
          visit_id?: string | null
        }
        Update: {
          appointment_id?: string | null
          clinic_patient_id?: string
          created_at?: string
          external_ref?: string | null
          flag?: string | null
          is_finalized?: boolean
          lab_provider?: string | null
          lab_result_id?: string
          panel_code?: string | null
          raw_payload?: Json | null
          reference_range_high?: number | null
          reference_range_low?: number | null
          requires_doctor_review?: boolean
          result_numeric?: number | null
          result_received_at?: string
          result_unit?: string | null
          result_value?: string | null
          reviewed_at?: string | null
          reviewed_by_staff_id?: string | null
          sample_collected_at?: string | null
          test_code?: string
          test_name?: string
          triage_classified_at?: string | null
          triage_group?: string
          triage_model?: string | null
          triage_reason?: string | null
          updated_at?: string
          visit_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "lab_result_appointment_id_fkey"
            columns: ["appointment_id"]
            isOneToOne: false
            referencedRelation: "appointment"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "lab_result_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "lab_result_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient_summary"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "lab_result_reviewed_by_staff_id_fkey"
            columns: ["reviewed_by_staff_id"]
            isOneToOne: false
            referencedRelation: "staff"
            referencedColumns: ["id"]
          },
        ]
      }
      mpi_merge_queue: {
        Row: {
          created_at: string | null
          id: string
          patient_id_a: string
          patient_id_b: string
          reviewed_at: string | null
          reviewed_by: string | null
          score: number
          status: string | null
        }
        Insert: {
          created_at?: string | null
          id?: string
          patient_id_a: string
          patient_id_b: string
          reviewed_at?: string | null
          reviewed_by?: string | null
          score: number
          status?: string | null
        }
        Update: {
          created_at?: string | null
          id?: string
          patient_id_a?: string
          patient_id_b?: string
          reviewed_at?: string | null
          reviewed_by?: string | null
          score?: number
          status?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "mpi_merge_queue_patient_id_a_fkey"
            columns: ["patient_id_a"]
            isOneToOne: false
            referencedRelation: "patient"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "mpi_merge_queue_patient_id_a_fkey"
            columns: ["patient_id_a"]
            isOneToOne: false
            referencedRelation: "patient_summary"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "mpi_merge_queue_patient_id_b_fkey"
            columns: ["patient_id_b"]
            isOneToOne: false
            referencedRelation: "patient"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "mpi_merge_queue_patient_id_b_fkey"
            columns: ["patient_id_b"]
            isOneToOne: false
            referencedRelation: "patient_summary"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "mpi_merge_queue_reviewed_by_fkey"
            columns: ["reviewed_by"]
            isOneToOne: false
            referencedRelation: "staff"
            referencedColumns: ["id"]
          },
        ]
      }
      patient: {
        Row: {
          address: string | null
          address_detail: string | null
          birth_year: number | null
          clinic_patient_id: string
          created_at: string | null
          date_of_birth: string | null
          ethnicity: string | null
          full_name: string
          full_name_unaccent: string | null
          gender: string | null
          guardian_name: string | null
          is_active: boolean | null
          linh_vuc: string | null
          location_id: string
          national_id_number: string | null
          nationality: string | null
          occupation: string | null
          patient_code: string
          patient_objection: string | null
          phone_primary: string | null
          phone_secondary: string | null
          province_code: string | null
          province_name: string | null
          updated_at: string | null
          van_de_di_kham: string | null
          ward_code: string | null
          ward_name: string | null
        }
        Insert: {
          address?: string | null
          address_detail?: string | null
          birth_year?: number | null
          clinic_patient_id?: string
          created_at?: string | null
          date_of_birth?: string | null
          ethnicity?: string | null
          full_name: string
          full_name_unaccent?: string | null
          gender?: string | null
          guardian_name?: string | null
          is_active?: boolean | null
          linh_vuc?: string | null
          location_id: string
          national_id_number?: string | null
          nationality?: string | null
          occupation?: string | null
          patient_code: string
          patient_objection?: string | null
          phone_primary?: string | null
          phone_secondary?: string | null
          province_code?: string | null
          province_name?: string | null
          updated_at?: string | null
          van_de_di_kham?: string | null
          ward_code?: string | null
          ward_name?: string | null
        }
        Update: {
          address?: string | null
          address_detail?: string | null
          birth_year?: number | null
          clinic_patient_id?: string
          created_at?: string | null
          date_of_birth?: string | null
          ethnicity?: string | null
          full_name?: string
          full_name_unaccent?: string | null
          gender?: string | null
          guardian_name?: string | null
          is_active?: boolean | null
          linh_vuc?: string | null
          location_id?: string
          national_id_number?: string | null
          nationality?: string | null
          occupation?: string | null
          patient_code?: string
          patient_objection?: string | null
          phone_primary?: string | null
          phone_secondary?: string | null
          province_code?: string | null
          province_name?: string | null
          updated_at?: string | null
          van_de_di_kham?: string | null
          ward_code?: string | null
          ward_name?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "patient_location_id_fkey"
            columns: ["location_id"]
            isOneToOne: false
            referencedRelation: "clinic_location"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "patient_province_code_fkey"
            columns: ["province_code"]
            isOneToOne: false
            referencedRelation: "province"
            referencedColumns: ["code"]
          },
          {
            foreignKeyName: "patient_ward_code_fkey"
            columns: ["ward_code"]
            isOneToOne: false
            referencedRelation: "ward"
            referencedColumns: ["code"]
          },
        ]
      }
      patient_contact_channel: {
        Row: {
          channel_type: string
          channel_value: string
          clinic_patient_id: string
          created_at: string | null
          id: string
          is_primary: boolean
          is_verified: boolean
          verified_at: string | null
        }
        Insert: {
          channel_type: string
          channel_value: string
          clinic_patient_id: string
          created_at?: string | null
          id?: string
          is_primary?: boolean
          is_verified?: boolean
          verified_at?: string | null
        }
        Update: {
          channel_type?: string
          channel_value?: string
          clinic_patient_id?: string
          created_at?: string | null
          id?: string
          is_primary?: boolean
          is_verified?: boolean
          verified_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "patient_contact_channel_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "patient_contact_channel_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient_summary"
            referencedColumns: ["clinic_patient_id"]
          },
        ]
      }
      patient_medical_profile: {
        Row: {
          allergies: string[] | null
          blood_type: string | null
          chronic_diseases: string[] | null
          clinic_patient_id: string
          created_at: string | null
          current_medications: string[] | null
          family_history: Json | null
          id: string
          notes: string | null
          surgical_history: string[] | null
          updated_at: string | null
        }
        Insert: {
          allergies?: string[] | null
          blood_type?: string | null
          chronic_diseases?: string[] | null
          clinic_patient_id: string
          created_at?: string | null
          current_medications?: string[] | null
          family_history?: Json | null
          id?: string
          notes?: string | null
          surgical_history?: string[] | null
          updated_at?: string | null
        }
        Update: {
          allergies?: string[] | null
          blood_type?: string | null
          chronic_diseases?: string[] | null
          clinic_patient_id?: string
          created_at?: string | null
          current_medications?: string[] | null
          family_history?: Json | null
          id?: string
          notes?: string | null
          surgical_history?: string[] | null
          updated_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "patient_medical_profile_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: true
            referencedRelation: "patient"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "patient_medical_profile_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: true
            referencedRelation: "patient_summary"
            referencedColumns: ["clinic_patient_id"]
          },
        ]
      }
      patient_next_of_kin: {
        Row: {
          clinic_patient_id: string
          created_at: string | null
          full_name: string
          id: string
          is_primary_contact: boolean
          notes: string | null
          phone: string | null
          relation: string
          updated_at: string | null
          zalo_id: string | null
        }
        Insert: {
          clinic_patient_id: string
          created_at?: string | null
          full_name: string
          id?: string
          is_primary_contact?: boolean
          notes?: string | null
          phone?: string | null
          relation: string
          updated_at?: string | null
          zalo_id?: string | null
        }
        Update: {
          clinic_patient_id?: string
          created_at?: string | null
          full_name?: string
          id?: string
          is_primary_contact?: boolean
          notes?: string | null
          phone?: string | null
          relation?: string
          updated_at?: string | null
          zalo_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "patient_next_of_kin_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "patient_next_of_kin_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient_summary"
            referencedColumns: ["clinic_patient_id"]
          },
        ]
      }
      payment: {
        Row: {
          amount: number | null
          clinic_patient_id: string | null
          created_at: string | null
          id: string
          kind: string
          paid_at: string | null
          paid_by_staff_id: string | null
          paid_by_text: string | null
          status: string
          updated_at: string | null
          visit_id: string
        }
        Insert: {
          amount?: number | null
          clinic_patient_id?: string | null
          created_at?: string | null
          id?: string
          kind: string
          paid_at?: string | null
          paid_by_staff_id?: string | null
          paid_by_text?: string | null
          status?: string
          updated_at?: string | null
          visit_id: string
        }
        Update: {
          amount?: number | null
          clinic_patient_id?: string | null
          created_at?: string | null
          id?: string
          kind?: string
          paid_at?: string | null
          paid_by_staff_id?: string | null
          paid_by_text?: string | null
          status?: string
          updated_at?: string | null
          visit_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "payment_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "payment_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient_summary"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "payment_paid_by_staff_id_fkey"
            columns: ["paid_by_staff_id"]
            isOneToOne: false
            referencedRelation: "staff"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "payment_visit_id_fkey"
            columns: ["visit_id"]
            isOneToOne: false
            referencedRelation: "visit"
            referencedColumns: ["visit_id"]
          },
        ]
      }
      pregnancy: {
        Row: {
          clinic_patient_id: string
          created_at: string | null
          edd_date: string | null
          gestational_age_at_registration: number | null
          high_risk_reason: string | null
          id: string
          is_high_risk: boolean | null
          lmp_date: string | null
          location_id: string
          outcome: string | null
          outcome_date: string | null
          primary_doctor_id: string | null
          updated_at: string | null
        }
        Insert: {
          clinic_patient_id: string
          created_at?: string | null
          edd_date?: string | null
          gestational_age_at_registration?: number | null
          high_risk_reason?: string | null
          id?: string
          is_high_risk?: boolean | null
          lmp_date?: string | null
          location_id: string
          outcome?: string | null
          outcome_date?: string | null
          primary_doctor_id?: string | null
          updated_at?: string | null
        }
        Update: {
          clinic_patient_id?: string
          created_at?: string | null
          edd_date?: string | null
          gestational_age_at_registration?: number | null
          high_risk_reason?: string | null
          id?: string
          is_high_risk?: boolean | null
          lmp_date?: string | null
          location_id?: string
          outcome?: string | null
          outcome_date?: string | null
          primary_doctor_id?: string | null
          updated_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "pregnancy_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "pregnancy_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient_summary"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "pregnancy_location_id_fkey"
            columns: ["location_id"]
            isOneToOne: false
            referencedRelation: "clinic_location"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "pregnancy_primary_doctor_id_fkey"
            columns: ["primary_doctor_id"]
            isOneToOne: false
            referencedRelation: "staff"
            referencedColumns: ["id"]
          },
        ]
      }
      prescription: {
        Row: {
          caution: string | null
          clinic_patient_id: string | null
          created_at: string | null
          dosage_instructions: string | null
          drug_catalog_ref: string | null
          drug_name_raw: string | null
          id: string
          quantity: string | null
          quantity_note: string | null
          source_ref: string
          standardized_form: string | null
          updated_at: string | null
          visit_id: string | null
          visit_link_raw: string | null
        }
        Insert: {
          caution?: string | null
          clinic_patient_id?: string | null
          created_at?: string | null
          dosage_instructions?: string | null
          drug_catalog_ref?: string | null
          drug_name_raw?: string | null
          id?: string
          quantity?: string | null
          quantity_note?: string | null
          source_ref: string
          standardized_form?: string | null
          updated_at?: string | null
          visit_id?: string | null
          visit_link_raw?: string | null
        }
        Update: {
          caution?: string | null
          clinic_patient_id?: string | null
          created_at?: string | null
          dosage_instructions?: string | null
          drug_catalog_ref?: string | null
          drug_name_raw?: string | null
          id?: string
          quantity?: string | null
          quantity_note?: string | null
          source_ref?: string
          standardized_form?: string | null
          updated_at?: string | null
          visit_id?: string | null
          visit_link_raw?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "prescription_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "prescription_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient_summary"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "prescription_visit_id_fkey"
            columns: ["visit_id"]
            isOneToOne: false
            referencedRelation: "visit"
            referencedColumns: ["visit_id"]
          },
        ]
      }
      province: {
        Row: {
          code: string
          code_name: string | null
          full_name: string
          name: string
        }
        Insert: {
          code: string
          code_name?: string | null
          full_name: string
          name: string
        }
        Update: {
          code?: string
          code_name?: string | null
          full_name?: string
          name?: string
        }
        Relationships: []
      }
      schema_migrations: {
        Row: {
          applied_at: string | null
          filename: string
        }
        Insert: {
          applied_at?: string | null
          filename: string
        }
        Update: {
          applied_at?: string | null
          filename?: string
        }
        Relationships: []
      }
      service_log: {
        Row: {
          clinic_patient_id: string | null
          created_at: string | null
          created_by_text: string | null
          finished_at: string | null
          id: string
          kind: string | null
          ordered_at: string | null
          patient_link_raw: string | null
          performer_text: string | null
          result_form_url: string | null
          result_text: string | null
          sent_to_lab_at: string | null
          service_name_raw: string | null
          service_type_id: string | null
          source_ref: string
          started_at: string | null
          status: string | null
          updated_at: string | null
          visit_link_raw: string | null
        }
        Insert: {
          clinic_patient_id?: string | null
          created_at?: string | null
          created_by_text?: string | null
          finished_at?: string | null
          id?: string
          kind?: string | null
          ordered_at?: string | null
          patient_link_raw?: string | null
          performer_text?: string | null
          result_form_url?: string | null
          result_text?: string | null
          sent_to_lab_at?: string | null
          service_name_raw?: string | null
          service_type_id?: string | null
          source_ref: string
          started_at?: string | null
          status?: string | null
          updated_at?: string | null
          visit_link_raw?: string | null
        }
        Update: {
          clinic_patient_id?: string | null
          created_at?: string | null
          created_by_text?: string | null
          finished_at?: string | null
          id?: string
          kind?: string | null
          ordered_at?: string | null
          patient_link_raw?: string | null
          performer_text?: string | null
          result_form_url?: string | null
          result_text?: string | null
          sent_to_lab_at?: string | null
          service_name_raw?: string | null
          service_type_id?: string | null
          source_ref?: string
          started_at?: string | null
          status?: string | null
          updated_at?: string | null
          visit_link_raw?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "service_log_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "service_log_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient_summary"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "service_log_service_type_id_fkey"
            columns: ["service_type_id"]
            isOneToOne: false
            referencedRelation: "service_type"
            referencedColumns: ["id"]
          },
        ]
      }
      service_price: {
        Row: {
          active: boolean
          category: string | null
          created_at: string | null
          group: string
          id: string
          name: string
          service_code: string
          tang: string | null
          unit_price: number | null
          updated_at: string | null
        }
        Insert: {
          active?: boolean
          category?: string | null
          created_at?: string | null
          group: string
          id?: string
          name: string
          service_code: string
          tang?: string | null
          unit_price?: number | null
          updated_at?: string | null
        }
        Update: {
          active?: boolean
          category?: string | null
          created_at?: string | null
          group?: string
          id?: string
          name?: string
          service_code?: string
          tang?: string | null
          unit_price?: number | null
          updated_at?: string | null
        }
        Relationships: []
      }
      service_type: {
        Row: {
          code: string
          created_at: string | null
          default_duration_minutes: number | null
          id: string
          is_active: boolean | null
          name: string
        }
        Insert: {
          code: string
          created_at?: string | null
          default_duration_minutes?: number | null
          id?: string
          is_active?: boolean | null
          name: string
        }
        Update: {
          code?: string
          created_at?: string | null
          default_duration_minutes?: number | null
          id?: string
          is_active?: boolean | null
          name?: string
        }
        Relationships: []
      }
      staff: {
        Row: {
          auth_user_id: string | null
          created_at: string | null
          employment_type: string
          full_name: string
          id: string
          is_active: boolean | null
          is_training: boolean | null
          primary_department: string
          primary_location_id: string | null
          short_name: string | null
          updated_at: string | null
        }
        Insert: {
          auth_user_id?: string | null
          created_at?: string | null
          employment_type?: string
          full_name: string
          id?: string
          is_active?: boolean | null
          is_training?: boolean | null
          primary_department: string
          primary_location_id?: string | null
          short_name?: string | null
          updated_at?: string | null
        }
        Update: {
          auth_user_id?: string | null
          created_at?: string | null
          employment_type?: string
          full_name?: string
          id?: string
          is_active?: boolean | null
          is_training?: boolean | null
          primary_department?: string
          primary_location_id?: string | null
          short_name?: string | null
          updated_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "staff_primary_location_id_fkey"
            columns: ["primary_location_id"]
            isOneToOne: false
            referencedRelation: "clinic_location"
            referencedColumns: ["id"]
          },
        ]
      }
      staff_capability: {
        Row: {
          capability: string
          created_at: string
          id: string
          proficiency_level: string
          staff_id: string
        }
        Insert: {
          capability: string
          created_at?: string
          id?: string
          proficiency_level?: string
          staff_id: string
        }
        Update: {
          capability?: string
          created_at?: string
          id?: string
          proficiency_level?: string
          staff_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "staff_capability_staff_id_fkey"
            columns: ["staff_id"]
            isOneToOne: false
            referencedRelation: "staff"
            referencedColumns: ["id"]
          },
        ]
      }
      staff_task: {
        Row: {
          assigned_to: string | null
          completed_at: string | null
          created_at: string
          description: string | null
          due_at: string | null
          location_id: string | null
          priority: string
          sla_hours: number
          source_id: string | null
          source_type: string | null
          status: string
          task_id: string
          task_type: string
          title: string
          updated_at: string
        }
        Insert: {
          assigned_to?: string | null
          completed_at?: string | null
          created_at?: string
          description?: string | null
          due_at?: string | null
          location_id?: string | null
          priority?: string
          sla_hours?: number
          source_id?: string | null
          source_type?: string | null
          status?: string
          task_id?: string
          task_type: string
          title: string
          updated_at?: string
        }
        Update: {
          assigned_to?: string | null
          completed_at?: string | null
          created_at?: string
          description?: string | null
          due_at?: string | null
          location_id?: string | null
          priority?: string
          sla_hours?: number
          source_id?: string | null
          source_type?: string | null
          status?: string
          task_id?: string
          task_type?: string
          title?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "staff_task_assigned_to_fkey"
            columns: ["assigned_to"]
            isOneToOne: false
            referencedRelation: "staff"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "staff_task_location_id_fkey"
            columns: ["location_id"]
            isOneToOne: false
            referencedRelation: "clinic_location"
            referencedColumns: ["id"]
          },
        ]
      }
      ultrasound_record: {
        Row: {
          clinic_patient_id: string
          created_at: string
          findings: Json | null
          gestational_age_weeks: number | null
          image_refs: string[] | null
          impression: string | null
          performed_at: string | null
          performed_by: string | null
          pregnancy_id: string | null
          ultrasound_id: string
          ultrasound_type: string | null
          updated_at: string
          visit_id: string
        }
        Insert: {
          clinic_patient_id: string
          created_at?: string
          findings?: Json | null
          gestational_age_weeks?: number | null
          image_refs?: string[] | null
          impression?: string | null
          performed_at?: string | null
          performed_by?: string | null
          pregnancy_id?: string | null
          ultrasound_id?: string
          ultrasound_type?: string | null
          updated_at?: string
          visit_id: string
        }
        Update: {
          clinic_patient_id?: string
          created_at?: string
          findings?: Json | null
          gestational_age_weeks?: number | null
          image_refs?: string[] | null
          impression?: string | null
          performed_at?: string | null
          performed_by?: string | null
          pregnancy_id?: string | null
          ultrasound_id?: string
          ultrasound_type?: string | null
          updated_at?: string
          visit_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "ultrasound_record_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "ultrasound_record_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient_summary"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "ultrasound_record_performed_by_fkey"
            columns: ["performed_by"]
            isOneToOne: false
            referencedRelation: "staff"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "ultrasound_record_pregnancy_id_fkey"
            columns: ["pregnancy_id"]
            isOneToOne: false
            referencedRelation: "pregnancy"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "ultrasound_record_visit_id_fkey"
            columns: ["visit_id"]
            isOneToOne: false
            referencedRelation: "visit"
            referencedColumns: ["visit_id"]
          },
        ]
      }
      visit: {
        Row: {
          appointment_id: string | null
          attending_doctor_id: string | null
          checked_in_at: string | null
          checked_in_by: string | null
          clinic_patient_id: string
          created_at: string
          finalized_at: string | null
          finalized_by: string | null
          location_id: string | null
          service_type_id: string | null
          status: string
          updated_at: string
          visit_id: string
          work_session_id: string | null
        }
        Insert: {
          appointment_id?: string | null
          attending_doctor_id?: string | null
          checked_in_at?: string | null
          checked_in_by?: string | null
          clinic_patient_id: string
          created_at?: string
          finalized_at?: string | null
          finalized_by?: string | null
          location_id?: string | null
          service_type_id?: string | null
          status?: string
          updated_at?: string
          visit_id?: string
          work_session_id?: string | null
        }
        Update: {
          appointment_id?: string | null
          attending_doctor_id?: string | null
          checked_in_at?: string | null
          checked_in_by?: string | null
          clinic_patient_id?: string
          created_at?: string
          finalized_at?: string | null
          finalized_by?: string | null
          location_id?: string | null
          service_type_id?: string | null
          status?: string
          updated_at?: string
          visit_id?: string
          work_session_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "visit_appointment_id_fkey"
            columns: ["appointment_id"]
            isOneToOne: false
            referencedRelation: "appointment"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "visit_attending_doctor_id_fkey"
            columns: ["attending_doctor_id"]
            isOneToOne: false
            referencedRelation: "staff"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "visit_checked_in_by_fkey"
            columns: ["checked_in_by"]
            isOneToOne: false
            referencedRelation: "staff"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "visit_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "visit_clinic_patient_id_fkey"
            columns: ["clinic_patient_id"]
            isOneToOne: false
            referencedRelation: "patient_summary"
            referencedColumns: ["clinic_patient_id"]
          },
          {
            foreignKeyName: "visit_finalized_by_fkey"
            columns: ["finalized_by"]
            isOneToOne: false
            referencedRelation: "staff"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "visit_location_id_fkey"
            columns: ["location_id"]
            isOneToOne: false
            referencedRelation: "clinic_location"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "visit_service_type_id_fkey"
            columns: ["service_type_id"]
            isOneToOne: false
            referencedRelation: "service_type"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "visit_work_session_id_fkey"
            columns: ["work_session_id"]
            isOneToOne: false
            referencedRelation: "work_session"
            referencedColumns: ["id"]
          },
        ]
      }
      visit_amendment: {
        Row: {
          amended_at: string
          amended_by: string
          amendment_id: string
          corrected_fields: string[]
          corrected_values: Json
          original_values: Json
          reason: string
          visit_id: string
        }
        Insert: {
          amended_at?: string
          amended_by: string
          amendment_id?: string
          corrected_fields: string[]
          corrected_values: Json
          original_values: Json
          reason: string
          visit_id: string
        }
        Update: {
          amended_at?: string
          amended_by?: string
          amendment_id?: string
          corrected_fields?: string[]
          corrected_values?: Json
          original_values?: Json
          reason?: string
          visit_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "visit_amendment_amended_by_fkey"
            columns: ["amended_by"]
            isOneToOne: false
            referencedRelation: "staff"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "visit_amendment_visit_id_fkey"
            columns: ["visit_id"]
            isOneToOne: false
            referencedRelation: "visit"
            referencedColumns: ["visit_id"]
          },
        ]
      }
      ward: {
        Row: {
          code: string
          code_name: string | null
          full_name: string
          name: string
          province_code: string
        }
        Insert: {
          code: string
          code_name?: string | null
          full_name: string
          name: string
          province_code: string
        }
        Update: {
          code?: string
          code_name?: string | null
          full_name?: string
          name?: string
          province_code?: string
        }
        Relationships: [
          {
            foreignKeyName: "ward_province_code_fkey"
            columns: ["province_code"]
            isOneToOne: false
            referencedRelation: "province"
            referencedColumns: ["code"]
          },
        ]
      }
      work_roster: {
        Row: {
          created_at: string | null
          id: string
          reject_reason: string | null
          shift: string
          sort: number
          staff_id: string | null
          staff_name: string
          station: string
          status: string
          updated_at: string | null
          week_start: string
          work_date: string
        }
        Insert: {
          created_at?: string | null
          id?: string
          reject_reason?: string | null
          shift?: string
          sort?: number
          staff_id?: string | null
          staff_name: string
          station: string
          status?: string
          updated_at?: string | null
          week_start: string
          work_date: string
        }
        Update: {
          created_at?: string | null
          id?: string
          reject_reason?: string | null
          shift?: string
          sort?: number
          staff_id?: string | null
          staff_name?: string
          station?: string
          status?: string
          updated_at?: string | null
          week_start?: string
          work_date?: string
        }
        Relationships: [
          {
            foreignKeyName: "work_roster_staff_id_fkey"
            columns: ["staff_id"]
            isOneToOne: false
            referencedRelation: "staff"
            referencedColumns: ["id"]
          },
        ]
      }
      work_session: {
        Row: {
          created_at: string | null
          end_time: string
          id: string
          location_id: string
          max_patients: number | null
          session_date: string
          session_type: string
          start_time: string
        }
        Insert: {
          created_at?: string | null
          end_time: string
          id?: string
          location_id: string
          max_patients?: number | null
          session_date: string
          session_type: string
          start_time: string
        }
        Update: {
          created_at?: string | null
          end_time?: string
          id?: string
          location_id?: string
          max_patients?: number | null
          session_date?: string
          session_type?: string
          start_time?: string
        }
        Relationships: [
          {
            foreignKeyName: "work_session_location_id_fkey"
            columns: ["location_id"]
            isOneToOne: false
            referencedRelation: "clinic_location"
            referencedColumns: ["id"]
          },
        ]
      }
      work_session_staff: {
        Row: {
          created_at: string | null
          id: string
          is_training: boolean
          on_call_flag: boolean
          role: string
          staff_id: string
          station: string
          work_session_id: string
        }
        Insert: {
          created_at?: string | null
          id?: string
          is_training?: boolean
          on_call_flag?: boolean
          role: string
          staff_id: string
          station: string
          work_session_id: string
        }
        Update: {
          created_at?: string | null
          id?: string
          is_training?: boolean
          on_call_flag?: boolean
          role?: string
          staff_id?: string
          station?: string
          work_session_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "work_session_staff_staff_id_fkey"
            columns: ["staff_id"]
            isOneToOne: false
            referencedRelation: "staff"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "work_session_staff_work_session_id_fkey"
            columns: ["work_session_id"]
            isOneToOne: false
            referencedRelation: "work_session"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      patient_summary: {
        Row: {
          clinic_patient_id: string | null
          date_of_birth: string | null
          full_name: string | null
          last_lab_received_at: string | null
          last_lab_test_code: string | null
          last_lab_triage_group: string | null
          last_visit_at: string | null
          national_id_number: string | null
          next_appointment_at: string | null
          next_appointment_status: string | null
          patient_code: string | null
          phone_primary: string | null
          total_visits: number | null
        }
        Relationships: []
      }
    }
    Functions: {
      doctor_patient_count: { Args: { p_doctor_id: string }; Returns: number }
      doctor_patient_list: {
        Args: {
          p_doctor_id: string
          p_limit?: number
          p_offset?: number
          p_term?: string
        }
        Returns: {
          clinic_patient_id: string
          created_at: string
          date_of_birth: string
          full_name: string
          patient_code: string
          phone_primary: string
          total_count: number
        }[]
      }
      f_unaccent: { Args: { "": string }; Returns: string }
      show_limit: { Args: never; Returns: number }
      show_trgm: { Args: { "": string }; Returns: string[] }
      unaccent: { Args: { "": string }; Returns: string }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  graphql_public: {
    Enums: {},
  },
  public: {
    Enums: {},
  },
} as const

