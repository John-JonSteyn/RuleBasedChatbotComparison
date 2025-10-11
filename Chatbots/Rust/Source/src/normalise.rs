use std::collections::HashMap;

/// Remove simple HTML tags by skipping anything between '<' and '>'.
pub fn strip_html_tags(input_text: &str) -> String {
    let mut output_text = String::with_capacity(input_text.len());
    let mut inside_tag = false;

    for character in input_text.chars() {
        match character {
            '<' => inside_tag = true,
            '>' => inside_tag = false,
            _ if !inside_tag => output_text.push(character),
            _ => {}
        }
    }
    output_text
}

/// Decode a safe subset of HTML entities
pub fn decode_basic_entities(input_text: &str) -> String {
    let mut named_map: HashMap<&'static str, char> = HashMap::new();
    named_map.insert("amp", '&');
    named_map.insert("lt", '<');
    named_map.insert("gt", '>');
    named_map.insert("quot", '"');
    named_map.insert("#39", '\'');

    let mut output_text = String::with_capacity(input_text.len());
    let mut entity_buffer = String::new();
    let mut inside_entity = false;

    let mut characters = input_text.chars().peekable();
    while let Some(character) = characters.next() {
        if character == '&' {
            inside_entity = true;
            entity_buffer.clear();
            continue;
        }

        if inside_entity {
            if character == ';' {
                let entity_text = entity_buffer.as_str();

                if let Some(stripped) = entity_text.strip_prefix("#") {
                    if let Ok(code_point) = stripped.parse::<u32>() {
                        if let Some(decoded) = char::from_u32(code_point) {
                            output_text.push(decoded);
                        } else {
                            output_text.push_str("&");
                            output_text.push_str(entity_text);
                            output_text.push(';');
                        }
                    } else if let Some(hex_str) = stripped.strip_prefix('x').or_else(|| stripped.strip_prefix('X')) {
                        if let Ok(code_point) = u32::from_str_radix(hex_str, 16) {
                            if let Some(decoded) = char::from_u32(code_point) {
                                output_text.push(decoded);
                            } else {
                                output_text.push_str("&");
                                output_text.push_str(entity_text);
                                output_text.push(';');
                            }
                        } else {
                            output_text.push_str("&");
                            output_text.push_str(entity_text);
                            output_text.push(';');
                        }
                    } else {
                        output_text.push_str("&");
                        output_text.push_str(entity_text);
                        output_text.push(';');
                    }
                } else if let Some(decoded) = named_map.get(entity_text) {
                    output_text.push(*decoded);
                } else {
                    output_text.push_str("&");
                    output_text.push_str(entity_text);
                    output_text.push(';');
                }

                inside_entity = false;
            } else {
                entity_buffer.push(character);
            }
        } else {
            output_text.push(character);
        }
    }

    if inside_entity {
        output_text.push('&');
        output_text.push_str(&entity_buffer);
    }

    output_text
}

/// Escape angle brackets so raw HTML cannot render in the console or any renderer.
pub fn escape_angle_brackets(input_text: &str) -> String {
    let mut output_text = String::with_capacity(input_text.len());
    for character in input_text.chars() {
        match character {
            '<' => output_text.push_str("&lt;"),
            '>' => output_text.push_str("&gt;"),
            _ => output_text.push(character),
        }
    }
    output_text
}

/// Pipeline for text used in matching
pub fn normalise_for_matching(input_text: &str) -> String {
    let without_tags = strip_html_tags(input_text);
    let decoded_text = decode_basic_entities(&without_tags);
    let lowercased_text = decoded_text.to_lowercase();
    lowercased_text.trim().to_string()
}

/// Pipeline for text used in display
pub fn normalise_for_display(input_text: &str) -> String {
    let escaped_text = escape_angle_brackets(input_text);
    escaped_text.trim().to_string()
}
