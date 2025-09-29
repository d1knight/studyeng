from graphviz import Digraph

# Создаем диаграмму
dot = Digraph(comment="ER Diagram for Education Platform", format="png")
dot.attr(rankdir="LR", size="8")

# Узлы (модели)
dot.node("User", "User\n(id, first_name, last_name, phone_number, tg_id, ...)")
dot.node("Course", "Course\n(id, name, description)")
dot.node("CourseTariff", "CourseTariff\n(id, name, description, price)")
dot.node("Chapter", "Chapter\n(id, order_index, name, passing_score)")
dot.node("Topic", "Topic\n(id, order_index, name, video_path, content)")
dot.node("Exercise", "Exercise\n(id, order_index, type)")
dot.node("Question", "Question\n(id, text, correct_answer)")
dot.node("UserChapter", "UserChapter\n(id, is_active, is_open)")
dot.node("UserQuestion", "UserQuestion\n(id, user_answer, is_correct, answered_at)")
dot.node("Payment", "Payment\n(id, amount, status, receipt, created_at)")

# Связи
dot.edge("Course", "CourseTariff", label="1 → *")
dot.edge("Course", "Chapter", label="1 → *")
dot.edge("Chapter", "Topic", label="1 → *")
dot.edge("Topic", "Exercise", label="1 → *")
dot.edge("Exercise", "Question", label="1 → *")
dot.edge("User", "UserChapter", label="1 → *")
dot.edge("Chapter", "UserChapter", label="1 → *")
dot.edge("User", "UserQuestion", label="1 → *")
dot.edge("Question", "UserQuestion", label="1 → *")
dot.edge("User", "Payment", label="1 → *")
dot.edge("CourseTariff", "Payment", label="1 → *")

# Сохраняем и визуализируем
file_path = "/mnt/data/er_diagram"
dot.render(file_path, view=False)

file_path + ".png"



    # def render_with_inputs(self):
        """Заменяет {{blank1}}, {{blank2}} на input-поля"""
        text = self.text

        def replace_placeholder(match):
            blank = match.group(1)
            answers = self.correct_answer.get(blank, [])
            if isinstance(answers, list):
                answers_str = "|".join(answers)
            else:
                answers_str = str(answers)
            return (
                f'<input type="text" class="answer-field form-control d-inline w-auto" '
                f'name="{blank}_{self.id}" data-correct="{answers_str}">'
            )

        rendered = re.sub(r"\{\{(blank\d+)\}\}", replace_placeholder, text)
        return mark_safe(rendered)