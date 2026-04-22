import re

class Anonymizer:
    def __init__(self):
        # Patrones específicos para datos de contacto
        self.patterns = {
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone": r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b',
            "dni": r'\b\d{8}[A-HJ-NP-TV-Z]\b',
            "linkedin": r'linkedin\.com/in/\S+',
            "github": r'github\.com/\S+'
        }

    def anonymize(self, text: str) -> str:
        if not text:
            return ""
        
        # 1. Primero aplicamos los Regex sobre todo el texto
        temp_text = text
        for key, pattern in self.patterns.items():
            label = f"[{key.upper()}_OCULTO]"
            temp_text = re.sub(pattern, label, temp_text)
            
        # 2. Ahora aplicamos la limpieza de cabecera sobre el texto ya procesado
        lines = temp_text.split('\n')
        new_lines = []
        
        # Analizamos las primeras 3 líneas para ocultar nombre/apellidos
        for i, line in enumerate(lines):
            clean_line = line.strip()
            
            # Filtro inteligente: solo ocultamos si es de las primeras líneas
            # y no parece ser el inicio de una sección importante
            if i < 3 and len(clean_line) > 0:
                keywords_perfil = ['perfil', 'resumen', 'experiencia', 'objetivo', 'sobre mí', 'contacto']
                if not any(key in clean_line.lower() for key in keywords_perfil):
                    new_lines.append("[DATO_IDENTIDAD_OCULTO]")
                    continue
            
            new_lines.append(line)
        
        return '\n'.join(new_lines)