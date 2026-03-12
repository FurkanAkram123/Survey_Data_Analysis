import json
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter
import os
import re

# Set matplotlib to use a font that handles unicode better
plt.rcParams['font.sans-serif'] = ['Courier New', 'DejaVu Sans', 'Arial', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False  # Prevent unicode minus rendering issues
plt.rcParams['font.monospace'] = ['Courier New']

# Function to normalize text and replace special characters with ASCII
def normalize_text(text):
    # Replace ALL types of dashes with the word "to" using unicode escape codes
    import re
    # Use unicode escape codes for all dash variants
    text = text.replace('\u2010', ' to ')  # hyphen
    text = text.replace('\u2011', ' to ')  # non-breaking hyphen
    text = text.replace('\u2012', ' to ')  # figure dash
    text = text.replace('\u2013', ' to ')  # en-dash
    text = text.replace('\u2014', ' to ')  # em-dash
    text = text.replace('\u2015', ' to ')  # horizontal bar
    text = text.replace('\u2212', ' to ')  # minus sign
    text = text.replace('-', ' to ')  # regular hyphen
    
    # Replace all spaces with regular space
    text = re.sub(r'[\u2009\u202f\u00a0\s]+', ' ', text)
    # Replace quotes
    text = text.replace('\u2018', "'")
    text = text.replace('\u2019', "'")
    text = text.replace('\u201c', '"')
    text = text.replace('\u201d', '"')
    
    # Remove any character that's not standard ASCII (except common punctuation)
    text = ''.join(c if ord(c) < 128 else '' for c in text)
    
    # Clean up multiple spaces
    text = ' '.join(text.split())
    return text

# Function to clean titles by removing bracketed content
def clean_title(text):
    # Remove anything inside parentheses/brackets
    text = re.sub(r'\s*[\(\[].*?[\)\]]\s*', ' ', text)
    # Clean up multiple spaces
    text = ' '.join(text.split())
    return text

# Get the directory where the script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(script_dir, 'Survey_results.js.txt')

# Load JSON
with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Print number of survey participants based on question 1 answer count
if data and 'answers' in data[0]:
    respondents = len(data[0]['answers'])
else:
    respondents = 0
print(f"Loaded survey data from {respondents} respondents")

# Normalize all text in the data
for q in data:
    q['text'] = normalize_text(q['text'])
    q['answers'] = [normalize_text(a) for a in q['answers']]

# simple timezone inference based on location string
# this doesn't require external services; it's heuristic-based.
def infer_timezone(location):
    loc = location.lower()

    # US states / regions grouped by time zone
    pacific = ['california','ca','oregon','wa','washington','nevada','nv','oster']
    mountain = ['colorado','co','utah','ut','wyoming','wy','montana','mt','idaho','id','new mexico','nm','arizona','az']
    central = ['texas','tx','oklahoma','ok','kansas','ks','nebraska','ne','south dakota','sd','north dakota','nd','louisiana','la','mississippi','ms','alabama','al','arkansas','ar']
    eastern = ['new york','ny','florida','fl','georgia','ga','north carolina','nc','south carolina','sc','virginia','va','pennsylvania','pa','ohio','oh','indiana','in','kentucky','ky','tennessee','tn','michigan','mi','maryland','md','district of columbia','dc','dc']
    
    # other common keywords
    if any(state in loc for state in pacific):
        return 'Pacific'
    if any(state in loc for state in mountain):
        return 'Mountain'
    if any(state in loc for state in central):
        return 'Central'
    if any(state in loc for state in eastern):
        return 'Eastern'
    
    # Canada provinces: approximate
    if 'ontario' in loc or 'quebec' in loc:
        return 'Eastern'
    if 'alberta' in loc or 'british columbia' in loc:
        return 'Pacific'
    if 'manitoba' in loc or 'saskatchewan' in loc:
        return 'Central'
    if 'nova scotia' in loc or 'new brunswick' in loc:
        return 'Atlantic'
    
    # fallback: look for simply timezone words
    if 'pst' in loc or 'pt' in loc:
        return 'Pacific'
    if 'mst' in loc:
        return 'Mountain'
    if 'cst' in loc:
        return 'Central'
    if 'est' in loc:
        return 'Eastern'
    return 'Other/Unknown'

# Bar plot for categorical
def plot_bar(q_num, q_text, answers):
    # replace any empty or whitespace-only answers with a placeholder
    cleaned = [(a if a.strip() else '(no response)') for a in answers]
    counts = Counter(cleaned)
    df = pd.DataFrame.from_dict(counts, orient='index', columns=['Count'])
    
    # Custom sorting: extract first number from labels for intelligent ordering
    def get_sort_key(label):
        if label == '(no response)':
            return (float('inf'), '')  # Push to end
        # Try to extract first number from label (e.g., "1 to 2 times" -> 1, "3 to 5 times" -> 3)
        match = re.search(r'(\d+)', label)
        if match:
            return (float(match.group(1)), label)
        # For non-numeric labels, sort alphabetically after numerics
        return (1000.0, label)
    
    try:
        sort_keys = [get_sort_key(idx) for idx in df.index]
        sort_indices = sorted(range(len(sort_keys)), key=lambda i: sort_keys[i])
        df = df.iloc[sort_indices]
    except Exception:
        pass
    
    # Convert counts to percentages
    total = df['Count'].sum()
    df_pct = (df['Count'] / total * 100).round(1)
    
    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.bar(range(len(df_pct)), df_pct.values)

    # Add percentage labels on top of each bar
    for i, (idx, val) in enumerate(df_pct.items()):
        ax.text(i, val + 1, f'{val}%', ha='center', va='bottom', fontsize=9)
    
    # Set y-axis limit to add white space at the top for labels
    max_val = df_pct.max()
    ax.set_ylim(0, max_val * 1.15)
    ax.set_xticks(range(len(df_pct)))
    ax.set_xticklabels(df_pct.index, rotation=45, ha='right', fontsize=9)
    ax.set_title(clean_title(q_text), wrap=True, fontsize=11)
    ax.set_ylabel('Percentage (%)')
    ax.set_xlabel('Response')
    plt.tight_layout()
    
    # Sanitize filename: remove invalid characters
    safe_name = ''.join(c for c in q_text[:20] if c not in r'<>:"/\|?*').replace(' ', '_')
    plt.savefig(f'Q{q_num}_{safe_name}_bar.png')
    plt.close()

# Open-ended questions
def summarize_open(q_num, q_text, answers):
    answers = [a.strip() for a in answers if a.strip()]
    if answers:
        counts = Counter(answers)
        df = pd.DataFrame.from_dict(counts, orient='index', columns=['Count']).sort_values('Count', ascending=False).head(10)
        print('Top responses:\n', df)
        all_text = ' '.join(answers).lower().split()
        word_counts = Counter(all_text)
        top_words = dict(word_counts.most_common(10))
        word_df = pd.DataFrame.from_dict(top_words, orient='index', columns=['Count'])
        fig, ax = plt.subplots(figsize=(12, 7))
        word_df.plot(kind='bar', legend=False, ax=ax)
        ax.set_title(f'Top Words: {q_text}', wrap=True, fontsize=11)
        ax.set_xlabel('')
        ax.tick_params(axis='x', labelsize=9)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        plt.tight_layout()
        safe_name = ''.join(c for c in q_text[:20] if c not in r'<>:"/\|?*').replace(' ', '_')
        plt.savefig(f'Q{q_num}_{safe_name}_words.png')
        plt.close()

# Plot complete answers for open-ended questions as a table
def plot_complete_answers(q_num, q_text, answers):
    import textwrap
    answers = [a.strip() for a in answers if a.strip()]
    if answers:
        counts = Counter(answers)
        df = pd.DataFrame.from_dict(counts, orient='index', columns=['Count']).sort_values('Count', ascending=False)
        df = df.reset_index()
        df.columns = ['Answer', 'Count']
        print('Top responses:\n', df.head(20))
        
        # wrap the answers to avoid cutoff
        wrap_width = 60
        df['Answer'] = df['Answer'].apply(lambda s: textwrap.fill(s, width=wrap_width))
        
        chunk_size = 20
        safe_name = ''.join(c for c in q_text[:20] if c not in r'<>:"/\|?*').replace(' ', '_')
        for idx_start in range(0, len(df), chunk_size):
            chunk = df.iloc[idx_start:idx_start+chunk_size]
            fig_height = 2 + len(chunk) * 0.5
            fig, ax = plt.subplots(figsize=(14, fig_height))
            ax.axis('tight')
            ax.axis('off')
            
            table_data = [['Answer', 'Count']]
            for _, row in chunk.iterrows():
                table_data.append([row['Answer'], str(int(row['Count']))])
            
            table = ax.table(cellText=table_data, cellLoc='left', loc='upper center',
                            colWidths=[0.85, 0.15], bbox=[0, 0.05, 1, 0.85])
            table.auto_set_font_size(False)
            table.set_fontsize(9)
    
            # adjust row height based on number of wrapped lines
            for r in range(len(table_data)):
                # count lines in the answer cell
                lines = table_data[r][0].count('\n') + 1
                # base height per line
                table[(r, 0)].set_height(0.3 * lines)
                table[(r, 1)].set_height(0.3 * lines)
            table.scale(1, 1)  # overall scale is now 1 since we set heights manually
            
            for j in range(2):
                table[(0, j)].set_facecolor('#40466e')
                table[(0, j)].set_text_props(weight='bold', color='white', ha='center')
            for r in range(1, len(table_data)):
                for c in range(2):
                    if r % 2 == 0:
                        table[(r, c)].set_facecolor('#f0f0f0')
                    else:
                        table[(r, c)].set_facecolor('white')
                    if c == 1:
                        table[(r, c)].set_text_props(ha='center')
            
            fig.suptitle(clean_title(q_text), fontsize=12, weight='bold', wrap=True, y=0.92)
            plt.subplots_adjust(top=0.90)
            plt.tight_layout()
            suffix = f"_{idx_start//chunk_size+1}" if len(df) > chunk_size else ''
            plt.savefig(f'Q{q_num}_{safe_name}_answers{suffix}.png', dpi=100, bbox_inches='tight')
            plt.close()

# Process
for q_num, q in enumerate(data, start=1):
    q_text = q['text']
    answers = q['answers']
    num_unique = len(set([a.strip() for a in answers if a.strip()]))
    # print both normal and repr to diagnose encoding issues
    print(f'\nQuestion {q_num}: {q_text}')
    print(f'Question repr: {repr(q_text)}')
    
    # special handling for question 2: convert location strings to timezones
    if q_num == 2:
        answers = [infer_timezone(a) for a in answers]
    counts = Counter(answers)
    df = pd.DataFrame.from_dict(counts, orient='index', columns=['Count']).sort_values('Count', ascending=False)
    print(df)
    
    # Check if this is an open-ended question that should be displayed as a table
    is_open_ended = any(keyword in q_text.lower() for keyword in ['specify', 'explain', 'describe', 'comment', 'other'])
    
    if is_open_ended or num_unique >= 15:
        plot_complete_answers(q_num, q_text, answers)
    else:
        plot_bar(q_num, q_text, answers)
